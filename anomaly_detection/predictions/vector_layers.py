from datetime import datetime, timedelta
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import F, Func, OuterRef, Subquery
from django.db.models.functions import JSONObject
from rest_framework.fields import JSONField
from vectortiles import VectorLayer

from anomaly_detection.regions.models import Municipality

from .models import Metric


class MetricMunicipalityVectorLayer(VectorLayer):
    queryset = Metric.objects.with_geometry()
    id = "metrics"
    tile_fields = ('anomaly_degree', 'id', 'region__name', 'value')
    min_zoom = 0
    geom_field = "region__geometry"

    def __init__(self, date, *args, **kwargs):
        if date is None:
            raise ValueError("Date is mandatory.")
        self.date = date
        super().__init__(*args, **kwargs)

    def get_vector_tile_queryset(self, *args, **kwargs):
        """
        Override the default get_vector_tile_queryset to filter by date.
        """
        return super().get_vector_tile_queryset(*args, **kwargs).filter(date=self.date).order_by()


class TimeSeriesMunicipalityVectorLayer(VectorLayer):
    """
    Vector layer for time series data of municipalities.
    """
    queryset = Metric.objects.with_geometry()
    id = "time_series_metrics"
    tile_fields = ('region__name', 'timeseries')
    min_zoom = 0
    geom_field = "geometry"

    def __init__(self, date, days, *args, **kwargs):
        if not date:
            raise ValueError("Date is mandatory.")
        if not days or days <= 0:
            raise ValueError("Days must be a positive integer.")
        self.date = datetime.strptime(date, "%Y-%m-%d").date()
        self.days = days
        super().__init__(*args, **kwargs)

    def get_vector_tile_queryset(self, *args, **kwargs):
        """
        Override the default get_vector_tile_queryset to return a list of municipalities
        """
        # Last 30 days of metrics for each municipality
        start_date = self.date - timedelta(days=self.days)
        # Define a JSONB cast wrapper

        class ArrayToJSON(Func):
            function = 'array_to_json'
            output_field = JSONField()
        # Aggregate into an array of JSON objects
        metric_entries_subquery = (
            Metric.objects
            .filter(
                region=OuterRef("pk"),
                date__gt=start_date,
                date__lte=self.date
            )
            .annotate(
                item=JSONObject(
                    id=F('id'),
                    date=F('date'),
                    value=F('value'),
                    anomaly_degree=F('anomaly_degree'),
                )
            )
            .values('region')  # required for ArrayAgg
            .annotate(
                timeseries=ArrayToJSON(ArrayAgg('item', ordering='date'))
            )
            .values('timeseries')
        )
        return (
            Municipality.objects
            .annotate(
                region__id=F("id"),
                region__name=F("name"),
                timeseries=Subquery(metric_entries_subquery[:1])
            )
        )
