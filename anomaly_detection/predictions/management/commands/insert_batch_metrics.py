import math
import os

import pandas as pd
from tqdm import tqdm
from django.core.management.base import BaseCommand
from django.db import transaction

from anomaly_detection.regions.models import Municipality
from anomaly_detection.predictions.models import Metric


class Command(BaseCommand):
    """
    Django command to insert metrics data into the database in batch.
    This command is intented to be used only once to initialize the database with metrics data.
    """

    help = """Load metrics data into the database."""

    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'bites')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            type=str,
            default=os.path.join(self.DATA_DIR),
            help='Path to the input CSV files'
        )

    def unify_metrics(self, files, *args, **kwargs):
        """
        Unify the metrics data from multiple CSV files into a single DataFrame.
        """
        # Initialize an empty list to hold the data
        dfs = []
        # Loop through the files
        for file in files:
            try:
                date = file.split("/")[-1].split("bites_")[1].split(".")[0]
                df_day = pd.read_csv(file)
                df_day["date"] = date
                dfs.append(df_day)
            except Exception as e:
                print(f"Error processing file {file}: {e}")

        # Create a DataFrame from the list of data
        df = pd.concat(dfs, ignore_index=True)
        del dfs
        return df

    def handle(self, *args, **options):
        """
        Handle the command to insert predictions data into the database.
        """
        directory = options['dir']

        # Collect all CSV file paths
        files = [
            os.path.join(root, file)
            for root, _, files in os.walk(directory)
            for file in files if file.endswith(".csv")
        ]
        if not files:
            self.stdout.write(self.style.ERROR("No CSV files found in the specified directory."))
            return
        print(f"Found {len(files)} files to process.")

        df = self.unify_metrics(files)
        print(f"Unified DataFrame shape: {df.shape}")
        print(df.head())

        codes = df['code'].unique()
        municipality_map = {
            m.code: m
            for m in Municipality.objects.filter(code__in=codes)
        }

        metrics_to_create = []
        for _, row in tqdm(df.iterrows(), total=len(df)):
            region = municipality_map.get(row['code'])
            if not region:
                continue  # Or log it as an issue

            try:
                metrics_to_create.append(Metric(
                    region=region,
                    date=row['date'],
                    value=row['est'] if not math.isnan(row['est']) else None,
                ))
            except Exception as e:
                print(f"Error creating Metric for row {row}: {e}")

        print(f"Total metrics to create: {len(metrics_to_create)}")
        print('Creating Metric objects, this may take a while...')

        with transaction.atomic():
            Metric.objects.bulk_create(metrics_to_create, batch_size=5000)
        self.stdout.write(self.style.SUCCESS("Successfully inserted metrics data into the database."))
