

import h3
from drf_spectacular.utils import (OpenApiParameter,
                                   OpenApiResponse, extend_schema)
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_nested.viewsets import NestedViewSetMixin

from src.metrics import filters, serializers
from src.metrics.models import (Metric, MetricSpatialDimension,
                                MetricTimeDimension, MetricValue)
from src.utils.geo import geojson_to_h3_shape


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

    class NestedMetricAttributeMixin(NestedViewSetMixin):
        """
        Mixin to add nested routing for metric attributes.
        """
        parent_lookup_kwargs = {
            'id': 'metric_id'
        }

        def get_serializer_context(self):
            context = super().get_serializer_context()
            context['metric'] = get_object_or_404(Metric.objects.all(), pk=self.request.data.get('metric_id'))
            return context

    class MetricValueViewSet(NestedMetricAttributeMixin, ListModelMixin, GenericViewSet):
        """
        ViewSet for MetricValue model.
        """
        queryset = MetricValue.objects.all()
        serializer_class = serializers.MetricValueSerializer
        permission_classes = [AllowAny]
        filterset_class = filters.MetricValueFilter

        @extend_schema(responses={202: OpenApiResponse(description='File accepted for processing')})
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
            The type is the type of the metric value (accepted values: "forecast", "reanalysis").
            The Regex pattern is:
            ^([a-zA-Z\\-]+)_((?:\\d{4}-\\d{2}-\\d{2})(?:T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2}))?)\\.csv$\n

            The content of the CSV file should be in the format: **h3_index, value**,
            where "h3_index" (hexadecimal string) is the H3 index of the cell and "value" (float) is the estimated value
            for that cell.\n
            """
            id = kwargs.get('id')
            serializer = self.get_serializer(data=request.FILES, context={'id': id})
            serializer.is_valid(raise_exception=True)

            serializer_response = serializer.save()

            return Response(
                serializer_response,
                status=status.HTTP_202_ACCEPTED
            )

        @extend_schema(
            operation_id="metrics_values_aggregate_by_geometry",
            request=serializers.GeoJSONModelSerializer,
            parameters=[
                OpenApiParameter(
                    name='time_after',
                    type=str,
                    location=OpenApiParameter.QUERY,
                    description='Start datetime (ISO8601)'
                ),
                OpenApiParameter(
                    name='time_before',
                    type=str,
                    location=OpenApiParameter.QUERY,
                    description='End datetime (ISO8601)'
                ),
            ],
            responses={
                200: OpenApiResponse(
                    description="Aggregated metric values by geometry",
                    response=serializers.MetricValueAggregateResponseSerializer,
                )}
        )
        @action(
            methods=['POST'],
            detail=False,
            url_path='aggregate_by_geometry',
            url_name='aggregate-by-geometry',
            filterset_class=filters.MetricValueFilterByPolygon
        )
        def aggregate_by_geometry(self, request, *args, **kwargs):
            """
            Action that filters metric values by a given geometry (Polygon or MultiPolygon)
            and aggregate its values by h3_index.
            The geometry should be provided in the request body as GeoJSON format.
            """
            # TODO: Check permissions, maybe we don't want to allow any user to filter by geometry
            # Validate that metric exists
            metric = get_object_or_404(Metric.objects.all(), pk=kwargs.get('id'))

            # Validate geometry
            req_serializer = serializers.GeoJSONModelSerializer(data=request.data)
            req_serializer.is_valid(raise_exception=True)
            geometry = req_serializer.validated_data['geometry']

            # Compute H3 indexes
            h3_shape = geojson_to_h3_shape(geometry)
            h3_indexes = list(h3.polygon_to_cells(h3shape=h3_shape, res=metric.h3_resolution))

            # Base queryset
            qs = self.get_queryset().filter(metric_id=metric.id).filter_by_polygon(
                geometry,
                resolution=metric.h3_resolution
            )

            # TODO: If req_serialzer.validate_date['time_FROM'] then qs = qs.filter(time__gte)
            # If req_serialzer.validate_date['time_TO'] then qs = qs.filter(time__lte)
            # TODO: Remove the following lines filterset
            # Apply filters
            filterset = filters.MetricValueFilterByPolygon(
                request.query_params,
                queryset=qs
            )
            if filterset.is_valid():
                qs = filterset.qs

            # Aggregate by time
            qs = qs.aggregate_mean_by_time()

            # Wrap response
            response_data = {
                "h3_indexes": h3_indexes,
                "values": qs,
            }

            # Serialize values
            response = serializers.MetricValueAggregateResponseSerializer(response_data).data

            return Response(response, status=status.HTTP_200_OK)

    class MetricSpatialDimensionViewSet(NestedMetricAttributeMixin, RetrieveModelMixin, GenericViewSet):
        """
        ViewSet for MetricSpatialDimension model.
        """
        queryset = MetricSpatialDimension.objects.all()
        serializer_class = serializers.MetricSpatialDimensionSerializer
        permission_classes = [AllowAny]
        lookup_field = 'h3_index'  # the actual model field
        # lookup_url_kwarg = 'h3_index'  # matches the router kwarg name

    class MetricTimeDimensionViewSet(NestedMetricAttributeMixin, ListModelMixin, GenericViewSet):
        """
        ViewSet for MetricTimeDimension model.
        """
        queryset = MetricTimeDimension.objects.all()
        serializer_class = serializers.MetricTimeDimensionSerializer
        permission_classes = [AllowAny]
        filterset_class = filters.MetricTimeDimensionFilter
