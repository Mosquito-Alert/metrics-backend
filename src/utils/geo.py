from django.contrib.gis.geos import MultiPolygon, Polygon
import h3


def geojson_to_h3_shape(geometry: dict):
    if isinstance(geometry, Polygon):
        exterior = [(y, x) for x, y in geometry.exterior_ring.coords]

        holes = [
            [(y, x) for x, y in geometry[i].coords]
            for i in range(1, len(geometry))  # interior rings
        ]

        return h3.LatLngPoly(exterior, holes)

    elif isinstance(geometry, MultiPolygon):
        polygons = []

        for poly in geometry:
            exterior = [(y, x) for x, y in poly.exterior_ring.coords]

            holes = [
                [(y, x) for x, y in poly[i].coords]
                for i in range(1, len(poly))
            ]

            polygons.append(h3.LatLngPoly(exterior, holes))

        return h3.LatLngMultiPoly(*polygons)

    else:
        raise ValueError(f"Unsupported geometry type: {type(geometry)}")
