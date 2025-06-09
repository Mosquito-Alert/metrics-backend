import math
import re
from datetime import datetime

import pandas as pd
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        SerializerMethodField)

from anomaly_detection.regions.models import Municipality
from anomaly_detection.regions.serializers import MunicipalitySerializer

from .models import Metric, Predictor


class MetricSerializer(ModelSerializer):
    """
    Serializer for the Metrics.
    """
    region_code = SerializerMethodField()

    def get_region_code(self, obj=None) -> str:
        return obj.region.code

    class Meta:
        model = Metric
        fields = ['id', 'date', 'value', 'predicted_value', 'lower_value', 'upper_value',
                  'anomaly_degree', 'region_code']
        read_only_fields = ['created_at', 'updated_at', 'anomaly_degree']


class MetricDetailSerializer(MetricSerializer):
    """
    Serializer for the Metric detail.
    """
    region = MunicipalitySerializer()

    class Meta(MetricSerializer.Meta):
        fields = ['id', 'date', 'value', 'predicted_value', 'lower_value', 'upper_value',
                  'anomaly_degree', 'region']


class MetricSeasonalitySerializer(ModelSerializer):
    """
    Serializer for the Metric Seasonality associated to the Predictor model.
    """
    yearly = serializers.ListField(source='yearly_seasonality')

    class Meta:
        model = Predictor
        fields = ['yearly']


class MetricTrendSerializer(ModelSerializer):
    """
    Serializer for the Metric Trend associated to the Predictor model.
    """
    date = serializers.DateTimeField(source='last_training_date', format='%Y-%m-%d')
    trend = serializers.ListField()

    class Meta:
        model = Predictor
        fields = ['date', 'trend']


class LastMetricDateSerializer(Serializer):
    """
    Serializer for the Metric Executions.
    """
    date = serializers.DateField()


class MetricFileSerializer(Serializer):
    """
    Serializer for uploading a file with a batch of metrics.
    """
    file = serializers.FileField()

    def validate_file(self, file):
        """
        Validate if the file is a CSV file and has the correct format.
        """
        # Check content type and extension
        if file.content_type != 'text/csv':
            raise ValidationError('Uploaded file must be a CSV file.')
        if not file.name.endswith('.csv'):
            raise ValidationError('File extension must be .csv')

        # Validate filename pattern
        pattern = r'^bites_(\d{4}-\d{2}-\d{2})\.csv$'
        match = re.match(pattern, file.name)
        if not match:
            raise ValidationError('Filename must match the format: bites_YYYY-MM-DD.csv')

        # Validate that date part is a real, valid date
        date_str = match.group(1)
        try:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if parsed_date > datetime.now().date():
                raise ValidationError('Date cannot be in the future.')
        except ValueError:
            raise ValidationError(f"Invalid date in filename: {date_str}")

        # Store the extracted date in validated_data
        self.context['filename_date'] = parsed_date

        return file

    def create(self, validated_data):
        """
        Create the metrics contained in the CSV file.
        """
        file = validated_data['file']
        date = self.context.get('filename_date')

        try:
            df = pd.read_csv(file)
        except Exception as e:
            raise ValidationError(f"Error reading CSV: {str(e)}")

        # Validate content
        required_columns = {'code', 'est'}
        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)
            raise ValidationError(f'Missing required columns: {", ".join(missing)}')
        if df.empty:
            raise ValidationError("The uploaded CSV file is empty — no rows found.")

        region_code_to_id = {obj.code: obj.id for obj in Municipality.objects.all()}

        metrics_to_create = []
        for idx, row in df.iterrows():
            metrics_to_create.append(
                Metric(
                    region_id=region_code_to_id[row['code']],
                    date=date,
                    value=row['est'] if not math.isnan(row['est']) else None,
                )
            )

        # Create the metrics without the prediction values
        objs = Metric.objects.bulk_create(metrics_to_create, batch_size=2000)

        # Perform prediction for each metric
        for i, metric in enumerate(objs):
            # An update per metric won't represent a significant delta in progress,
            # so it will be updated each 10th metric prediction for performance reasons
            if i % 10 == 0 or i == len(objs) - 1:
                metric.refresh_prediction(refresh_progress=True)
            else:
                metric.refresh_prediction(refresh_progress=False)
        return objs
