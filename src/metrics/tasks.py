import os
from celery import shared_task
import pandas as pd
from rest_framework.exceptions import ValidationError

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

    # --- Ensure time dimension exists ---
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
        batch_size=2000
    )

    # TODO: Check if the len of the created objects is the same as the prepared ones

    time_dimension.total_cells = len(metrics_to_create)
    time_dimension.save()

    # --- Refresh predictions once all metrics are created ---
    for metric in metrics_to_create:
        metric.refresh_prediction()

    clean_file(file_path)

    print(f"MetricValues created successfully for time {time}.")
