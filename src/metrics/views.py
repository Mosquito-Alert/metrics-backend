

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
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
                    description="Grouped by h3_index",
                    response={
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/MetricValueSerializer"}
                        }
                    },
                    examples=[
                        OpenApiExample(
                            name="Grouped response example",
                            value={
                                "863944607ffffff": [
                                    {
                                        "time": "2025-09-05T00:00:00Z",
                                        "value": 4.87,
                                        "prediction": None
                                    }
                                ]
                            },
                            response_only=True,)
                    ]
                )}
        )
        @action(
            methods=['POST'],
            detail=False,
            url_path='filter_by_geometry',
            url_name='filter-by-geometry',
            filterset_class=filters.MetricValueFilterByPolygon
        )
        def filter_by_geometry(self, request, *args, **kwargs):
            """
            Action that filters metric values by a given geometry (Polygon or MultiPolygon).
            The geometry should be provided in the request body as GeoJSON format.
            """
            # validate that metrid_id exists
            metric = get_object_or_404(Metric.objects.all(), pk=kwargs.get('id'))

            # Use gis serializer to validate the geometry
            req_serializer = serializers.GeoJSONModelSerializer(data=request.data)
            req_serializer.is_valid(raise_exception=True)

            geometry = req_serializer.validated_data['geometry']

            qs = self.get_queryset().filter(metric_id=metric.id).filter_by_polygon(
                geometry,
                resolution=metric.h3_resolution
            )

            # APPLY FILTERSET MANUALLY # CHECK: There is a way of doing it without applying manually? Same with swagger
            filterset = filters.MetricValueFilterByPolygon(
                request.query_params,
                queryset=qs
            )
            if filterset.is_valid():
                qs = filterset.qs

            # result = self.get_serializer(qs, many=True).data
            result = serializers.MetricValueGroupedSerializer(qs).data
            return Response(result, status=status.HTTP_200_OK)

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
