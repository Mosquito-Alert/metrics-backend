import os
import re
import uuid
from datetime import datetime, timezone

from dateutil import parser
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ModelSerializer, Serializer, defaultdict
from rest_framework_gis.fields import GeometryField

from src.metrics.tasks import create_metric_values
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


class GeoJSONModelSerializer(serializers.Serializer):
    """Serializer for validating GeoJSON geometries."""
    geometry = GeometryField()

    class Meta:
        fields = ['geometry']


class MetricValuePredictorSerializer(serializers.ModelSerializer):
    """
    Serializer for the predicted values of a MetricValue instance.
    """

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


class MetricValueSerializer(ModelSerializer):
    """
    Serializer for the Metric Values.
    """
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


class MetricValueGroupedSerializer(serializers.Serializer):
    def to_representation(self, data):
        grouped = defaultdict(list)

        items = MetricValueSerializer(data, many=True).data

        for item in items:
            h3_index = item.pop('h3_index')
            grouped[h3_index].append(item)

        return dict(grouped)


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
        (Async) Creates the metric values contained in the CSV file.
        """
        file = validated_data['file']
        time = self.context.get('filename_datetime')
        type = self.context.get('filename_type')
        metric = self.context.get('metric')

        temp_dir = os.environ.get('SHARED_TEMP_DIR', "/tmp")
        unique_name = f"{uuid.uuid4()}.csv"
        file_path = os.path.join(temp_dir, unique_name)

        # Temporary save the file
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        task_res = create_metric_values.delay(file_path=file_path,
                                              time=time, type=type, metric_id=metric.id)
        return {
            "status": "Processing started in background.",
            "task_id": task_res.id
        }
