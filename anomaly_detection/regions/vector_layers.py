from vectortiles import VectorLayer
from .models import AutonomousCommunity, Municipality, Province


class AutonomousCommunityLayer(VectorLayer):
    model = AutonomousCommunity
    id = "autonomous_communities"
    tile_fields = ('code', "name")
    min_zoom = 0
    geom_field = "geometry"


class ProvinceVectorLayer(VectorLayer):
    model = Province
    id = "provinces"
    tile_fields = ('code', "name")
    min_zoom = 0
    geom_field = "geometry"


class MunicipalityVectorLayer(VectorLayer):
    model = Municipality  # your model, (you can use queryset or get_queryset method instead)
    id = "municipalities"  # layer id in you vector layer. each class attribute can be defined by get_{attribute} method
    tile_fields = ('code', "name")  # fields to include in tile
    # minimum zoom level to include layer. Take care of this, as it could be a performance issue.
    # Try to not embed data that will no be shown in your style definition.
    min_zoom = 0
    # all attributes available in vector layer definition can be defined
    geom_field = "geometry"


class RegionProvinceVectorLayer(ProvinceVectorLayer):
    min_zoom = 5
    max_zoom = 7


class RegionMunicipalityVectorLayer(MunicipalityVectorLayer):
    min_zoom = 8
