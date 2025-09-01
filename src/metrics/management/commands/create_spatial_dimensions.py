
import os
import pandas as pd
from django.core.management.base import BaseCommand

from src.metrics.models import MetricSpatialDimension

# TODO: Another command that updates spatial dimensions


class Command(BaseCommand):
    """
    Django command to create all the spatial dimensions for a metric.
    This command accepts a metric ID as an argument and a CSV file path that contains
    the spatial dimensions to create.
    """

    help = """Django command to create all the spatial dimensions for a metric.
    This command accepts a metric ID as an argument and a CSV file path that contains
    the spatial dimensions to create. The CSV file must contain at least the column 'h3_index'.
    """

    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

    def add_arguments(self, parser):
        parser.add_argument('metric_id', type=int, help='ID of the metric to create spatial dimensions for')
        parser.add_argument('csv_file', type=str, help='Path to the CSV file containing spatial dimensions')
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        """
        Handle the command to create spatial dimensions for a metric, given a metric ID and a CSV file.
        """
        metric_id = options['metric_id']
        csv_file = options['csv_file']

        # Open the CSV file
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to read CSV file: {e}'))
            return

        n_dimensions = self.create_spatial_dimensions(metric_id, df)
        self.stdout.write(self.style.SUCCESS(f'Successfully created {n_dimensions} spatial dimensions.'))

    def create_spatial_dimensions(self, metric_id, df) -> int:
        """
        Create spatial dimensions for a metric based on the provided DataFrame.
        """
        try:
            dimensions = []
            # The DataFrame will contain at least the following column: h3_index. Other columns will be ignored.
            for h3_index in df["h3_index"].values:
                dimension = MetricSpatialDimension(metric_id=metric_id, h3_index=h3_index)
                dimension.clean()
                dimensions.append(dimension)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to create spatial dimensions: {e}'))
            return 0
        MetricSpatialDimension.objects.bulk_create(dimensions, batch_size=2000)
        return len(dimensions)
