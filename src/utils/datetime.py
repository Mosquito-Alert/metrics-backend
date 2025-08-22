from datetime import datetime, timedelta


def generate_date_range(start_str, end_str, fmt='%Y-%m-%d'):
    """
    Generate dates between start_str and end_str (inclusive).

    Args:
        start_str (str): The start date as a string.
        end_str (str): The end date as a string.
        fmt (str): The date format (default '%Y-%m-%d').

    Yields:
        datetime.date: The dates in the range.
    """
    start_date = datetime.strptime(start_str, fmt).date()
    end_date = datetime.strptime(end_str, fmt).date()

    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def clean_time_field(datetime: datetime, metric) -> datetime:
    """
    Helper method to clean the time field.
    """
    from src.metrics import models
    cleaned_datetime = datetime.replace(second=0, microsecond=0)
    if metric.time_dimension_step == models.Metric.TimeDimensionStepType.HOURLY:
        cleaned_datetime = cleaned_datetime.replace(minute=0)
    elif metric.time_dimension_step == models.Metric.TimeDimensionStepType.DAILY:
        cleaned_datetime = cleaned_datetime.replace(hour=0, minute=0)
    return cleaned_datetime
