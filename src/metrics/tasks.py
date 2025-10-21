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

    # Convert res 6 → res 5 to optimise rasterization
    df["h3_parent"] = df["h3_index"].apply(lambda x: h3.cell_to_parent(x, 5))
    # Aggregate by parent index (mean temperature, or any aggregation)
    df_res5 = df.groupby("h3_parent", as_index=False)["value"].mean()
    df_res5.reset_index(drop=True, inplace=True)

    # Filter out cells crossing the antimeridian
    df_res5["latlong"] = df_res5["h3_parent"].apply(lambda x: h3.cell_to_boundary(x))

    def long_diff_exceeds_180(latlong_tuple):
        longs = [lon for _, lon in latlong_tuple]
        return not (max(longs) - min(longs)) > 180
    filtered_df = df_res5[df_res5["latlong"].apply(long_diff_exceeds_180)].reset_index(drop=True)

    # Convert h3_index from hex string to integer
    filtered_df["h3_parent"] = filtered_df["h3_parent"].astype(str).apply(lambda x: int(x, 16))

    # Convert to PyArrow arrays
    h3_array = pa.array(filtered_df["h3_parent"])
    val_array = pa.array(filtered_df["value"].round(1))

    # Rasterize
    nodata_value = -1
    array, transform = rasterize_cells(
        h3_array,
        val_array,
        size=(10000, 10000),
        nodata_value=nodata_value
    )

    # Convert to 8-bit
    valid_mask = array != nodata_value
    if np.any(valid_mask):
        vmin, vmax = np.percentile(array[valid_mask], [1, 99])  # ignore outliers
        scaled = np.clip((array - vmin) / (vmax - vmin) * 255, 0, 255)
        array = scaled.astype(np.uint8)
    else:
        array = np.full_like(array, fill_value=0, dtype=np.uint8)

    # Time format to YYYY-MM-DDTHH:MM
    time = time_dimension.time.strftime("%Y-%m-%dT%H:%M")

    # Save to GeoTIFF and upload to S3
    temp_dir = os.environ.get('SHARED_TEMP_DIR', "/tmp")
    temp_tiff_path = f"{temp_dir}/{time_dimension.id}_raster.tiff"

    with rasterio.open(
        temp_tiff_path,
        "w",
        driver="COG",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        crs="EPSG:4326",
        transform=transform
    ) as dst:
        dst.write(array, 1)

    key = f"rasters/{time}.tiff"
    s3_client.upload_file(temp_tiff_path, settings.S3_BUCKET_NAME, key)
    clean_file(temp_tiff_path)

    print(f"Rasterization complete for time dimension {time_dimension.id}.")
