

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from src.metrics.models import Metric, MetricPredictionProgress, MetricValue
from src.metrics import serializers


class MetricViewSet(GenericViewSet, ListModelMixin):
    """
    ViewSet for Metric model.
    """
    queryset = Metric.objects.all()
    serializer_class = serializers.MetricSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name='from',
                type=OpenApiTypes.DATETIME,
                description='Filter results starting from this datetime.',
                required=False,
            ),
            OpenApiParameter(
                name='to',
                type=OpenApiTypes.DATETIME,
                description='Filter results ending at this datetime.',
                required=False,
            ),
            OpenApiParameter(
                name='h3_index',
                type=OpenApiTypes.STR,
                description='Filter result by this H3 Index.',
                required=False,
            ),
        ]
    ),
)
class ValueViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    ViewSet for MetricValue model.
    """
    queryset = MetricValue.objects.all()
    serializer_class = serializers.MetricValueSerializer
    permission_classes = [AllowAny]

    @action(
        methods=['GET'],
        detail=True,
        url_path='seasonality',
        url_name='seasonality',
        serializer_class=serializers.SeasonalitySerializer
    )
    def get_seasonality(self, *args, **kwargs):
        """
        Action that returns the seasonality of a specific metric value.
        """
        metric_value = self.get_object()
        predictor = getattr(metric_value, 'predictor', None)

        if predictor and (predictor.yearly_seasonality or
                          predictor.weekly_seasonality or
                          predictor.daily_seasonality):
            serializer = self.get_serializer(predictor)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(
            {"detail": f'No seasonality found for metric value (metric: {metric_value.metric.name}, h3 index: '
             f'{metric_value.h3_index}, time: {metric_value.time}).'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(
        methods=['GET'],
        detail=True,
        url_path='trend',
        url_name='trend',
        serializer_class=serializers.MetricTrendSerializer
    )
    def get_trend(self, *args, **kwargs):
        """
        Action that returns the trend of a specific metric.
        """
        metric_value = self.get_object()
        predictor = getattr(metric_value, 'predictor', None)
        if predictor and predictor.trend:
            serializer = self.get_serializer(predictor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": f'No trend for metric value (metric: {metric_value.metric.name}, h3 index: '
             f'{metric_value.h3_index}, time: {metric_value.time}).'},
            status=status.HTTP_404_NOT_FOUND
        )

    @extend_schema(
        responses=serializers.LastMetricDateSerializer(many=True),
    )
    @action(
        methods=['GET'],
        detail=False,
        url_path='dates',
        url_name='dates',
        serializer_class=serializers.LastMetricDateSerializer,
        pagination_class=None,
    )
    def list_dates(self, *args, **kwargs):
        """
        Action that returns the all the dates in which there are metrics available.
        """
        executions = MetricPredictionProgress.objects.filter(success_percentage__gte=0.95).order_by("-time").all()
        if executions:
            serializer = self.get_serializer(executions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "No executions found."},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(
        methods=['GET'],
        detail=False,
        url_path='dates/last',
        url_name='last-date',
        serializer_class=serializers.LastMetricDateSerializer
    )
    def get_last_date(self, *args, **kwargs):
        """
        Action that returns the last date in which there are metrics available.
        """
        last_execution = MetricPredictionProgress.objects.filter(success_percentage__gte=0.95).order_by("-time").first()
        if last_execution:
            serializer = self.get_serializer({"time": last_execution.time})
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "No executions found."},
            status=status.HTTP_404_NOT_FOUND
        )

    def get_queryset(self):
        """
        Optionally restricts the returned values to a given H3 index, type, or date range.
        """
        queryset = super().get_queryset()
        h3_index = self.request.query_params.get('h3_index')
        value_type = self.request.query_params.get('type')
        from_datetime = self.request.query_params.get('from')
        to_datetime = self.request.query_params.get('to')

        if h3_index:
            queryset = queryset.filter(h3_index=h3_index)
        if value_type:
            queryset = queryset.filter(type=value_type)
        if from_datetime:
            queryset = queryset.filter(time__gte=from_datetime)
        if to_datetime:
            queryset = queryset.filter(time__lte=to_datetime)

        return queryset
