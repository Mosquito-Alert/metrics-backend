from django.core.management.base import BaseCommand
from datetime import datetime

from src.metrics.models import Boundary
from src.metrics.tasks import predict_batch_task


class Command(BaseCommand):
    """
    Django command to update the predicted values in the Metric model, given their assigned predictor.
    """

    help = """Load metrics data into the database."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--h3-index',
            type=str,
            default=None,
            help='Filter by H3 index (e.g., "8928308280fffff")'
        )
        parser.add_argument(
            '--metric-id',
            type=int,
            default=None,
            help='Filter by metric ID'
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
        h3_index = options.get('h3_index')
        metric_id = options.get('metric_id')

        # TODO: Now we don't have a table with all the geographic boundaries, so this needs to be adapted
        # boundary_qs = Boundary.objects.all()
        # if h3_index:
        #     boundary_qs = boundary_qs.filter(h3_index=h3_index)

        # for boundary in boundary_qs.iterator(chunk_size=1000):
        #     predict_batch_task.delay(from_date=from_date, to_date=to_date, boundary_id=boundary.id, metric_id=metric_id)
