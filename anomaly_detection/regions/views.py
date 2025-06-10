from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from vectortiles.mixins import BaseVectorTileView
from vectortiles.rest_framework.renderers import MVTRenderer

from anomaly_detection.regions.models import AutonomousCommunity, Municipality, Province
from anomaly_detection.regions.serializers import MunicipalityRetrieveSerializer, MunicipalitySerializer
from anomaly_detection.regions.vector_layers import (
    AutonomousCommunityLayer,
    MunicipalityVectorLayer,
    ProvinceVectorLayer,
    RegionMunicipalityVectorLayer,
    RegionProvinceVectorLayer
)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name='region_name',
                type=OpenApiTypes.STR,
                description='Region name.',
                required=False,
                default='Lloret de Mar'
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['name', '-name', 'province', '-province', 'code', '-name',],
                description='Order by `code`, `name` or `province`.',
            ),

        ]
    ),
)
class RegionViewSet(BaseVectorTileView, GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    ViewSet for the Municipality model with MVT rendering.
    """
    queryset = Municipality.objects
    serializer_class = MunicipalitySerializer
    layer_classes = [RegionMunicipalityVectorLayer, RegionProvinceVectorLayer, AutonomousCommunityLayer]

    @action(
        methods=['GET'],
        detail=False,
        renderer_classes=(MVTRenderer, ),
        url_path=r'tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',  # TODO: Remove trailing slash (only in this method)
        url_name='tiles')
    def get_tiles(self, request, z, x, y, *args, **kwargs):
        """
        Action that returns the tiles of a specified region and zoom. This endpoint is dynamic, so it will return
        the tiles for a municipality, province, or autonomous community based on the zoom level.
        """
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    @action(
        methods=['GET'],
        detail=False,
        layer_classes=[AutonomousCommunityLayer],
        renderer_classes=(MVTRenderer, ),
        queryset=AutonomousCommunity.objects.all(),
        url_path=r'autonomous_communities/tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',
        url_name='autonomous_communities_tiles')
    def get_tiles_autonomous_communities(self, request, z, x, y, *args, **kwargs):
        """
        Action that returns the tiles of a specified autonomous community and zoom
        """
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    @action(
        methods=['GET'],
        detail=False,
        layer_classes=[ProvinceVectorLayer],
        renderer_classes=(MVTRenderer, ),
        queryset=Province.objects.all(),
        url_path=r'provinces/tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',
        url_name='provinces_tiles')
    def get_tiles_provinces(self, request, z, x, y, *args, **kwargs):
        """
        Action that returns the tiles of a specified province and zoom
        """
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    @action(
        methods=['GET'],
        detail=False,
        layer_classes=[MunicipalityVectorLayer],
        renderer_classes=(MVTRenderer, ),
        queryset=Municipality.objects.all(),
        url_path=r'municipalities/tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)',
        url_name='municipalities_tiles')
    def get_tiles_municipalities(self, request, z, x, y, *args, **kwargs):
        """
        Action that returns the tiles of a specified municipality and zoom
        """
        z, x, y = int(z), int(x), int(y)
        content, status = self.get_content_status(z, x, y)
        return Response(content, status=status)

    def get_queryset(self):
        """
        Override the default queryset to filter by region name if provided.
        """
        queryset = super().get_queryset()
        region_name = self.request.query_params.get('region_name', None)
        geometry = self.request.query_params.get('geometry', None)
        if self.action == 'retrieve' and geometry and geometry.lower() == 'true':
            queryset = queryset.with_geometry()
        if region_name:
            queryset = queryset.filter(name__icontains=region_name)
        return queryset.all()

    def get_serializer(self, *args, **kwargs):
        """
        Override the default serializer to include geometry if requested.
        """
        if self.action == 'retrieve':
            return MunicipalityRetrieveSerializer(*args, **kwargs)
        return super().get_serializer(*args, **kwargs)
