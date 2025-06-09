from django.core.management.base import BaseCommand
from datetime import datetime

from anomaly_detection.regions.models import Municipality
from anomaly_detection.predictions.tasks import predict_batch_task


class Command(BaseCommand):
    """
    Django command to update the predicted values in the Metric model, given their assigned predictor.
    """

    help = """Load metrics data into the database."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--region',
            type=str,
            default=None,
            help='Filter by region (e.g., "ESP.1.1.1.1_1")'
        )
        parser.add_argument(
            '--from-date',
            type=str,
            default="2000-01-01",
            help='Start date for filtering metrics (format: YYYY-MM-DD)'
        )
        parser.add_argument(
            '--to-date',
            type=str,
            default=datetime.now().strftime('%Y-%m-%d'),
            help='End date for filtering metrics (format: YYYY-MM-DD)'
        )

    def handle(self, *args, **options):
        """
        Handle the command to insert predictions data into the database.
        """

        from_date = options.get('from_date')
        to_date = options.get('to_date')
        region = options.get('region')

        region_qs = Municipality.objects.all()
        if region:
            region_qs = region_qs.filter(code=region)

        for region in region_qs.iterator(chunk_size=1000):
            predict_batch_task.delay(from_date=from_date, to_date=to_date, region_id=region.id)
