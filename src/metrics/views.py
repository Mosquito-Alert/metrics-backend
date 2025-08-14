

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from src.metrics.models import Metric, MetricValue, MetricStatistics, Predictor
from src.metrics import filters, serializers


class MetricViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    ViewSet for Metric model.
    """
    queryset = Metric.objects.all()
    serializer_class = serializers.MetricSerializer
    permission_classes = [AllowAny]
    filterset_class = None
    lookup_url_kwarg = "id"

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.MetricListSerializer
        return super().get_serializer_class()


@extend_schema_view(
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
    lookup_url_kwarg = "id"

    def get_queryset(self):
        """
        Override to filter by metric_id.
        """
        queryset = super().get_queryset()
        metric_id = self.kwargs.get('metric_id')
        if metric_id:
            queryset = queryset.filter(metric_id=metric_id)
        return queryset

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
        # TODO: Catch the error if intergrity error is raised (ex: metric_id does not exist)

        return Response(
            {"detail": f"File processed successfully. {len(created_metrics_values)} metric values created"},
            status=status.HTTP_201_CREATED
        )


class MetricPredictorViewSet(GenericViewSet, RetrieveModelMixin):
    """
    ViewSet for MetricPredictor model.
    """
    queryset = Predictor.objects.all()
    serializer_class = serializers.PredictorSerializer
    permission_classes = [AllowAny]
    lookup_field = 'h3_index'  # the actual model field
    lookup_url_kwarg = 'h3_index'  # matches the router kwarg name

    def get_object(self):
        queryset = self.get_queryset()

        metric_id = self.kwargs['metric_id']
        h3_index = self.kwargs['h3_index']

        obj = queryset.get(metric_id=metric_id, h3_index=h3_index)
        self.check_object_permissions(self.request, obj)
        return obj


class MetricStatisticsViewSet(GenericViewSet, ListModelMixin):
    """
    ViewSet for MetricStatistics model.
    """
    queryset = MetricStatistics.objects.all()
    serializer_class = serializers.MetricStatisticsSerializer
    permission_classes = [AllowAny]
    filterset_class = filters.MetricStatisticsFilter
    lookup_url_kwarg = "id"
