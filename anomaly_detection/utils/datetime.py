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
