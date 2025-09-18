import re
from datetime import datetime, timezone
from dateutil import parser
import pandas as pd

from rest_framework import serializers
from rest_framework.serializers import (ModelSerializer, Serializer)
from rest_framework.exceptions import ValidationError

from src.utils.datetime import clean_time_field

from . import models


class MetricListSerializer(ModelSerializer):
    """
    Serializer for listing the Metrics.
    """
    class Meta:
        model = models.Metric
        fields = ['id', 'name', 'code']
        read_only_fields = ['created_at', 'updated_at']


class MetricSerializer(ModelSerializer):
    """
    Serializer for Metric.
    """
    time_dimension_step = serializers.ChoiceField(choices=[
        x.lower() for x in models.Metric.TimeDimensionStepType.names])

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['time_dimension_step'] = [
            x.name.lower() for x in models.Metric.TimeDimensionStepType
        ][0]
        return ret

    class Meta:
        model = models.Metric
        fields = ['id', 'name', 'code', 'time_dimension_step', 'is_predictable']
        read_only_fields = ['created_at', 'updated_at']


class MetricValueSerializer(ModelSerializer):
    """
    Serializer for the Metric Values.
    """
    class MetricValuePredictorSerializer(serializers.ModelSerializer):
        def to_representation(self, instance):
            if self.allow_null and instance.predicted_value is None:
                return None
            return super().to_representation(instance)

        class Meta:
            model = models.MetricValue
            fields = ['value', 'lower_confidence_band', 'upper_confidence_band', 'anomaly_degree']
            extra_kwargs = {
                'value': {'source': 'predicted_value', 'required': True, 'allow_null': False},
                'lower_confidence_band': {'required': True, 'allow_null': True},
                'upper_confidence_band': {'required': True, 'allow_null': True},
                'anomaly_degree': {'required': True, 'allow_null': True}
            }

    prediction = MetricValuePredictorSerializer(source='*', read_only=True, allow_null=True)

    def get_prediction(self, obj):
        """
        Returns the predicted values for the metric value if available.
        """
        if hasattr(obj, 'predicted_value') and obj.predicted_value is not None:
            return {
                'value': obj.predicted_value,
                'lower_confidence_band': obj.lower_confidence_band,
                'upper_confidence_band': obj.upper_confidence_band,
                'anomaly_degree': obj.anomaly_degree
            }
        return None

    class Meta:
        model = models.MetricValue
        fields = ['h3_index', 'time', 'value',  'prediction']


class MetricSpatialDimensionSerializer(ModelSerializer):
    """
    Serializer for the MetricSpatialDimension model.
    """
    class Meta:
        model = models.MetricSpatialDimension
        fields = ['h3_index', 'trend', 'yearly_seasonality', 'weekly_seasonality', 'daily_seasonality']


class MetricTimeDimensionSerializer(ModelSerializer):
    """
    Serializer for the MetricTimeDimension model.
    """

    type = serializers.ChoiceField(choices=[x.lower() for x in models.MetricTimeDimension.MetricValueType.names])

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['type'] = [
            x.name.lower()
            for x in models.MetricTimeDimension.MetricValueType if x.value == instance.type
        ][0]
        return ret

    class Meta:
        model = models.MetricTimeDimension
        fields = ['time', 'prediction_progress', 'type']
        read_only_fields = ['prediction_progress']


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
        pattern = r'^([a-zA-Z\-]+)_((?:\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?)\.csv$'
        match = re.match(pattern, file.name)
        if not match:
            raise ValidationError('Filename must match the format: {type}_YYYY-MM-DD[TXX.XX.XXXZ].csv')

        # Validate that datetime part is a real valid datetime
        try:
            date_str = match.group(2)
            # Parse ISO 8601 date/time
            parsed_datetime = parser.isoparse(date_str)

            # Ensure it's timezone-aware
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)

            # Compare to now in UTC
            if parsed_datetime > datetime.now(timezone.utc):
                raise ValidationError('Date cannot be in the future.')
        except ValueError:
            raise ValidationError(f"Invalid date in filename: {date_str}")
        # Clean the time field
        metric_id = self.context.get('id')
        metric = models.Metric.objects.get(id=metric_id)
        self.context['filename_datetime'] = clean_time_field(parsed_datetime, metric)

        # Validate that the type of the metric is one of the accepted values
        try:
            metric_type = match.group(1)
            parsed_type = models.MetricTimeDimension.MetricValueType[metric_type.upper()].value
        except KeyError:
            raise ValidationError(
                f"Invalid metric type in filename: {metric_type}. Accepted values are: "
                f"{', '.join(models.MetricTimeDimension.MetricValueType._value2member_map_.keys())}")
        self.context['filename_type'] = parsed_type
        self.context['metric'] = metric

        return file

    def create(self, validated_data):
        """
        Create the metrics contained in the CSV file.
        """
        file = validated_data['file']
        time = self.context.get('filename_datetime')
        type = self.context.get('filename_type')
        metric = self.context.get('metric')

        # --- Prepare tracking sets ---
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
            df = pd.read_csv(file, usecols=["h3_index", "value"])
        except Exception as e:
            raise ValidationError(f"Error reading CSV: {str(e)}")

        required_columns = {'h3_index', 'value'}
        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)
            raise ValidationError(
                f'Missing required columns: {", ".join(missing)}'
            )

        if df.empty:
            raise ValidationError("The uploaded CSV file is empty — no rows found.")

        # --- Validate h3_index consistency ---
        h3_set = set(df["h3_index"].unique())
        if h3_set != db_h3:
            missing_in_db = h3_set - db_h3
            extra_in_db = db_h3 - h3_set
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
            obj.clean(metric)
            metrics_to_create.append(obj)

        print(f"Prepared {len(metrics_to_create)} MetricValue objects for bulk creation.")

        # --- Bulk insert for this chunk ---
        models.MetricValue.objects.bulk_create(
            metrics_to_create,
            # update_conflicts=True,
            # update_fields=["value"],
            # unique_fields=["metric_id", "h3_index", "time"],
            batch_size=2000
        )

        # TODO: Check if the len of the created objects is the same as the prepared ones

        time_dimension.total_cells = len(metrics_to_create)
        time_dimension.save()

        # --- Refresh predictions once all metrics are created ---
        for metric in metrics_to_create:
            metric.refresh_prediction()

        return metrics_to_create
