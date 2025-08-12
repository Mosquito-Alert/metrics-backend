

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from src.metrics.models import Metric, MetricPredictionProgress, MetricValue
from src.metrics import filters, serializers


class MetricViewSet(GenericViewSet, ListModelMixin):
    """
    ViewSet for Metric model.
    """
    queryset = Metric.objects.all()
    serializer_class = serializers.MetricSerializer
    permission_classes = [AllowAny]
    lookup_url_kwarg = "id"

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


@extend_schema_view(
    get_last_date=extend_schema(operation_id="metrics_last_date_retrieve"),
    post_batch_create=extend_schema(responses={201: OpenApiResponse(description='File processes successfully.')})
)
class MetricValueViewSet(GenericViewSet, ListModelMixin):
    """
    ViewSet for MetricValue model.
    """
    queryset = MetricValue.objects.all()
    serializer_class = serializers.MetricValueSerializer
    permission_classes = [AllowAny]
    filterset_class = filters.MetricValueFilter

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

    @action(
        methods=['POST'],
        detail=False,
        url_path='batch',
        url_name='batch',
        serializer_class=serializers.MetricFileSerializer,
        authentication_classes=[TokenAuthentication],
        permission_classes=[IsAuthenticated]
    )
    def post_batch_create(self, request, *args, **kwargs):
        """
        Action that creates a batch of metric values, and calls a Predictor model to predict values.\n

        The endpoint accepts a **CSV file** with the following filename format:
        "**{type}_YYYY-MM-DD[TXX.XX.XXXZ].csv**", where [TXX.XX.XXXZ] is the time part, which is optional, and
        where "Z" could be replaced by the timezone (+XX:XX).
        The type is the type of the metric (accepted values: "forecast", "reanalysis").
        The Regex pattern is:
        ^([a-zA-Z\\-]+)_((?:\\d{4}-\\d{2}-\\d{2})(?:T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2}))?)\\.csv$\n

        The content of the CSV file should be in the format: **h3_index, value**,
        where "h3_index" (hexadecimal string) is the H3 index of the cell and "value" (float) is the estimated value
        for that cell.\n
        """
        metric_id = kwargs.get('metric_id')
        serializer = self.get_serializer(data=request.FILES, context={'metric_id': metric_id})
        serializer.is_valid(raise_exception=True)

        created_metrics_values = serializer.save()

        return Response(
            {"detail": f"File processed successfully. {len(created_metrics_values)} metric values created"},
            status=status.HTTP_201_CREATED
        )
