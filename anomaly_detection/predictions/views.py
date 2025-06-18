from datetime import datetime
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiParameter, OpenApiResponse, extend_schema,
                                   extend_schema_view)
from rest_framework import filters, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from vectortiles.mixins import BaseTileJSONView, BaseVectorTileView
from vectortiles.rest_framework.renderers import MVTRenderer

from anomaly_detection.predictions.models import Metric, MetricPredictionProgress
from anomaly_detection.predictions.serializers import (
    LastMetricDateSerializer, MetricDetailSerializer, MetricFileSerializer,
    MetricSeasonalitySerializer, MetricSerializer, MetricTrendSerializer)
from anomaly_detection.predictions.vector_layers import (
    MetricMunicipalityVectorLayer,
    TimeSeriesMunicipalityVectorLayer
)


class BaseMetricTilesView():
    queryset = Metric.objects
    layer_classes = [MetricMunicipalityVectorLayer]
    authentication_classes = []  # No authentication required by default
    permission_classes = [AllowAny]  # Allow any user by default

    def get_layer_class_kwargs(self):
        date = self.request.query_params.get('date')
        days = self.request.query_params.get('days', 30)  # Default to 30 days if not provided

        if self.action == 'get_timeseries_tiles':
            return {'date': date, 'days': int(days)}
        return {'date': date}

    id = "features"
    tile_fields = ('anomaly_degree', )


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name='date_from',
                type=OpenApiTypes.DATE,
                description='Starting date from which the results will return.',
                required=False,
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATE,
                description='Ending date which to the results will return.',
                required=False,
            ),
            OpenApiParameter(
                name='region_code',
                type=OpenApiTypes.STR,
                description='Determines the region of the results (history).',
                required=False,
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['date', '-date'],
                description='Order by `date` (asc) or `-date` (desc)',
            ),
        ]
    ),
    get_tiles=extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                description='Date of the results to return.',
                required=True,
            ),
        ],
    ),
    get_timeseries_tiles=extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                description='Date of the results to return.',
                required=True,
            ),
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                description='Number of days to return in the time series.',
                required=False,
            ),
        ],
    ),
    get_last_date=extend_schema(operation_id="metrics_last_date_retrieve"),
    post_batch_create=extend_schema(responses={201: OpenApiResponse(description='File processes successfully.')})
)
class MetricViewSet(BaseMetricTilesView, BaseVectorTileView, GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    ViewSet for Metric model.
    """
    queryset = Metric.objects
    serializer_class = MetricSerializer
    authentication_classes = []  # No authentication required by default
    permission_classes = [AllowAny]  # Allow any user by default
    layer_classes = [MetricMunicipalityVectorLayer]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter
    ]
    ordering_fields = ['date']
    ordering = ['-date']

    id = "features"
    tile_fields = ('anomaly_degree', )

    def get_layers(self):
        try:
            return super().get_layers()
        except ValueError as e:
            raise ValidationError(e)

    @action(
        methods=['GET'],
        detail=False,
        renderer_classes=(MVTRenderer, ),
        url_path=r'tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',  # TODO: Remove trailing slash (only in this method)
        url_name='tiles')
    def get_tiles(self, request, z, x, y, *args, **kwargs):
        """
        Action that returns the tiles of a specified area and zoom
        """
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    @action(
        methods=['GET'],
        detail=False,
        renderer_classes=(MVTRenderer,),
        url_path=r'timeseries/tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',
        url_name='timeseries_tiles',
        layer_classes=[TimeSeriesMunicipalityVectorLayer]
    )
    def get_timeseries_tiles(self, request, z, x, y, *args, **kwargs):
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    @action(
        methods=['GET'],
        detail=False,
        url_path='dates/last',
        url_name='last-date',
        serializer_class=LastMetricDateSerializer
    )
    def get_last_date(self, *args, **kwargs):
        """
        Action that returns the last date in which there are metrics available.
        """
        last_execution = MetricPredictionProgress.objects.filter(success_percentage__gte=0.95).order_by("-date").first()
        if last_execution:
            serializer = self.get_serializer({"date": last_execution.date})
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "No executions found."},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(
        methods=['GET'],
        detail=True,
        url_path='seasonality',
        url_name='seasonality',
        serializer_class=MetricSeasonalitySerializer
    )
    def get_seasonality(self, *args, **kwargs):
        """
        Action that returns the seasonality of a specific metric.
        """
        metric = self.get_object()
        predictor = getattr(metric, 'predictor', None)
        if predictor and predictor.yearly_seasonality:
            serializer = self.get_serializer(predictor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": f'No seasonality for metric {metric.id} found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(
        methods=['GET'],
        detail=True,
        url_path='trend',
        url_name='trend',
        serializer_class=MetricTrendSerializer
    )
    def get_trend(self, *args, **kwargs):
        """
        Action that returns the trend of a specific metric.
        """
        metric = self.get_object()
        predictor = getattr(metric, 'predictor', None)
        if predictor and predictor.trend:
            serializer = self.get_serializer(predictor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": f'No trend for metric {metric.id} found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(
        methods=['POST'],
        detail=False,
        url_path='batch',
        url_name='batch',
        serializer_class=MetricFileSerializer,
        authentication_classes=[TokenAuthentication],
        permission_classes=[IsAuthenticated]
    )
    def post_batch_create(self, request, *args, **kwargs):
        """
        Action that creates a batch of metrics, and calls a Predictor model to predict values.\n
        The endpoint accepts a **CSV file** with the following filename format: **"bites_YYYY-MM-DD.csv**",
        and with the following columns: **[code, est]**.\n
        The CSV should contain every region for a specific day (specified in the filename), where
        the "code" is the region code and the "est" is the value.
        """
        serializer = self.get_serializer(data=request.FILES)
        serializer.is_valid(raise_exception=True)

        created_metrics = serializer.save()

        return Response(
            {"detail": f"File processed successfully. {len(created_metrics)} metrics created"},
            status=status.HTTP_201_CREATED
        )

    def get_queryset(self):
        """
        Override the get_queryset method to filter the queryset based on
        the method action and the request parameters.
        """
        queryset = super().get_queryset()

        if self.action == 'list':
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            region_code = self.request.query_params.get('region_code')
            if date_from:
                queryset = queryset.filter(date__gte=date_from)
            if date_to:
                queryset = queryset.filter(date__lte=date_to)
            if region_code:
                queryset = queryset.filter(region__code=region_code)

        return queryset.all()

    def get_serializer_class(self):
        """
        Override the get_serializer_class method to return the appropriate
        serializer class based on the method action and the request parameters.
        """
        if self.action == 'retrieve':
            return MetricDetailSerializer

        return super().get_serializer_class()


class TileJSONView(BaseMetricTilesView, BaseTileJSONView, APIView):
    tile_url = "http://localhost:8000/api/v1/metrics/timeseries/tiles/{{z}}/{{x}}/{{y}}/?date={date}&days={days}"

    def get_tile_url(self, date, days):
        return self.tile_url.format(
            date=date,
            days=days
        )

    def get_layer_class_kwargs(self):
        return {'date': datetime(year=2023, month=10, day=1)}

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                description='Date of the results to return.',
                required=True,
            ),
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                description='Number of days to return in the time series.',
                required=False,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        # self.request = request
        date = request.query_params.get('date')
        days = request.query_params.get('days', 30)
        return Response(self.get_tilejson(self.get_tile_url(date, days)))
