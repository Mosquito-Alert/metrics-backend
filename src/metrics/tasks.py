import os

import h3
import numpy as np
import pandas as pd
import pyarrow as pa
import rasterio
from celery import shared_task
from django.conf import settings
from h3ronpy.pandas.raster import rasterize_cells
from rest_framework.exceptions import ValidationError
from rasterio.warp import calculate_default_transform, reproject, Resampling

from project.s3 import s3_client
from src.metrics import models


def clean_file(file_path: str):
    """
    Deletes temporary file after processing.
    """
    if os.path.exists(file_path):
        os.remove(file_path)


@shared_task
def create_metric_values(file_path: str, time: str, type: str, metric_id: int):
    """
    Creates metric values from a given file.
    """
    metric = models.Metric.objects.get(id=metric_id)

    h3_set = set()

    previous_time_dimension = models.MetricTimeDimension.objects.filter(metric=metric, time=time).first()

    # --- Ensure time dimension exists - --
    time_dimension, _ = models.MetricTimeDimension.objects.update_or_create(
        metric=metric,
        time=time,
        defaults={'type': type}
    )

    if previous_time_dimension:
        print("Time dimension already has cells, deleting existing MetricValues for this time.")
        models.MetricValue.objects.filter(metric_id=metric.id, time=time).delete()
        time_dimension.total_cells = 0
        time_dimension.save()

    # --- Retrieve DB spatial dimensions ---
    spatial_dimensions = {
        sd.h3_index: sd
        for sd in models.MetricSpatialDimension.objects.filter(metric=metric).iterator(chunk_size=100000)
    }
    if not spatial_dimensions:
        raise ValidationError("No spatial dimensions found in DB for this metric.")

    db_h3 = set(spatial_dimensions.keys())

    # --- Validate CSV content and collect h3_index ---
    try:
        df = pd.read_csv(file_path, usecols=["h3_index", "value"])
    except Exception as e:
        clean_file(file_path)
        raise ValidationError(f"Error reading CSV: {str(e)}")

    required_columns = {'h3_index', 'value'}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        clean_file(file_path)
        raise ValidationError(
            f'Missing required columns: {", ".join(missing)}'
        )

    if df.empty:
        clean_file(file_path)
        raise ValidationError("The uploaded CSV file is empty — no rows found.")

    # --- Validate h3_index consistency ---
    h3_set = set(df["h3_index"].unique())
    if h3_set != db_h3:
        missing_in_db = h3_set - db_h3
        extra_in_db = db_h3 - h3_set
        clean_file(file_path)
        raise ValidationError({
            "missing_in_db": list(missing_in_db),
            "extra_in_db": list(extra_in_db),
        })

    # --- Build MetricValue objects ---
    metrics_to_create = []
    for row in df.itertuples(index=False, name=None):
        spatial_dimension = spatial_dimensions.get(row[0])
        if not spatial_dimension:
            # Should not happen, since we already validated h3_index
            continue
        obj = models.MetricValue(
            metric_id=metric.id,
            time=time_dimension.time,
            h3_index=spatial_dimension.h3_index,
            value=row[1] if pd.notna(row[1]) else None,
        )
        obj.clean(metric, bulk=True)
        metrics_to_create.append(obj)

    print(f"Prepared {len(metrics_to_create)} MetricValue objects for bulk creation, for {time}.")

    # --- Bulk insert for this chunk ---
    models.MetricValue.objects.bulk_create(
        metrics_to_create,
        batch_size=100_000
    )

    if len(metrics_to_create) != models.MetricValue.objects.filter(metric_id=metric.id, time=time).count():
        print("Mismatch in created MetricValue objects.")
        models.MetricValue.objects.filter(metric_id=metric.id, time=time).delete()
        time_dimension.total_cells = 0
        time_dimension.save()
        clean_file(file_path)
        raise ValidationError("Error creating MetricValue objects.")

    time_dimension.total_cells = len(metrics_to_create)
    time_dimension.save()

    # --- Refresh predictions once all metrics are created ---
    for metric in metrics_to_create:
        metric.refresh_prediction()

    clean_file(file_path)

    print(f"MetricValues created successfully for time {time}.")

    # TODO: Better to chain them when calling the first task. For that, see how to retrieve the task IDs.
    rasterize_cells_for_time_dimension.delay(time_dimension.id)


@shared_task
def rasterize_cells_for_time_dimension(time_dimension_id: int):
    """
    Rasterizes H3 cells for a given time (specified in the time dimension).
    """
    time_dimension = models.MetricTimeDimension.objects.get(id=time_dimension_id)

    print("Starting rasterization for time dimension:", time_dimension.id)

    metrics = models.MetricValue.objects.filter(
        metric_id=time_dimension.metric_id,
        time=time_dimension.time
    ).values("h3_index", "value").iterator(10000)

    df = pd.DataFrame.from_records(metrics)

    if df.empty:
        print("No MetricValues found for rasterization.")
        return

    # Filter out cells crossing the antimeridian
    df["latlong"] = df["h3_index"].apply(lambda x: h3.cell_to_boundary(x))

    def long_diff_exceeds_180(latlong_tuple):
        longs = [lon for _, lon in latlong_tuple]
        return not (max(longs) - min(longs)) > 180
    filtered_df = df[df["latlong"].apply(long_diff_exceeds_180)].reset_index(drop=True)

    # Convert h3_index from hex string to integer
    filtered_df["h3_index"] = filtered_df["h3_index"].astype(str).apply(lambda x: int(x, 16))

    # Convert to PyArrow arrays
    h3_array = pa.array(filtered_df["h3_index"])
    val_array = pa.array(filtered_df["value"].round(1))

    # Rasterize
    nodata_value = -1
    size = 10000
    array, transform = rasterize_cells(
        h3_array,
        val_array,
        size=(size, size),
        nodata_value=nodata_value
    )

    # Transform the val_array to float32
    array = array.astype(np.float32)

    # Reproject to 3857
    src_crs = "EPSG:4326"
    dst_crs = "EPSG:3857"
    height, width = size, size  # array.shape
    profile = {
        "driver": "GTiff",
        "dtype": array.dtype,
        "count": 1,
        "height": height,
        "width": width,
        "transform": transform,
        "crs": src_crs,
        "nodata": nodata_value,
    }
    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs, dst_crs, width, height, *rasterio.transform.array_bounds(height, width, transform)
    )
    dst_array = np.empty((dst_height, dst_width), dtype=array.dtype)
    reproject(
        source=array,
        destination=dst_array,
        src_transform=transform,
        src_nodata=nodata_value,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear
    )
    cog_profile = profile.copy()
    cog_profile.update({
        "driver": "COG",
        "dtype": dst_array.dtype,
        "height": dst_height,
        "width": dst_width,
        "count": 1,
        "crs": dst_crs,
        "transform": dst_transform,
        "compress": "deflate",
        "blockxsize": 256,
        "blockysize": 256,
        "tiled": True,
        "nodata": nodata_value
    })

    # Time format to YYYY-MM-DDTHH:MM
    time = time_dimension.time.strftime("%Y-%m-%dT%H:%M")

    # Save to GeoTIFF and upload to S3
    temp_dir = os.environ.get('SHARED_TEMP_DIR', "/tmp")
    temp_tiff_path = f"{temp_dir}/{time_dimension.id}_raster.tiff"

    with rasterio.open(temp_tiff_path, "w", **cog_profile) as dst:
        dst.write(dst_array, 1)

    key = f"rasters/{time}.tiff"
    s3_client.upload_file(temp_tiff_path, settings.S3_BUCKET_NAME, key)
    clean_file(temp_tiff_path)

    print(f"Rasterization complete for time dimension {time_dimension.id}.")
