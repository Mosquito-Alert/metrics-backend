from vectortiles import VectorLayer
from .models import Municipality, Province


class MunicipalityVectorLayer(VectorLayer):
    model = Municipality  # your model, as django conventions you can use queryset or get_queryset method instead)
    id = "municipalities"  # layer id in you vector layer. each class attribute can be defined by get_{attribute} method
    tile_fields = ('code', "name")  # fields to include in tile
    # minimum zoom level to include layer. Take care of this, as it could be a performance issue.
    # Try to not embed data that will no be shown in your style definition.
    min_zoom = 7
    # all attributes available in vector layer definition can be defined
    geom_field = "geometry"


class ProvinceVectorLayer(VectorLayer):
    model = Province  # your model, as django conventions you can use queryset or get_queryset method instead)
    id = "provinces"  # layer id in you vector layer. each class attribute can be defined by get_{attribute} method
    tile_fields = ('code', "name")  # fields to include in tile
    # minimum zoom level to include layer. Take care of this, as it could be a performance issue.
    # Try to not embed data that will no be shown in your style definition.
    min_zoom = 3
    max_zoom = 6
    # all attributes available in vector layer definition can be defined
    geom_field = "geometry"
