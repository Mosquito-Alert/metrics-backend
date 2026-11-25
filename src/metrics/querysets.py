from django.db.models import Avg
from rest_framework.generics import QuerySet
import h3


from src.utils.geo import geojson_to_h3_shape


class MetricValueQuerySet(QuerySet):

    def filter_by_polygon(self, geometry: dict, resolution: int):
        h3_shape = geojson_to_h3_shape(geometry)

        h3_indexes = h3.polygon_to_cells(h3shape=h3_shape, res=resolution)

        return self.filter(h3_index__in=h3_indexes)

    def aggregate_mean_by_time(self):
        return (
            self
            .values('time')
            .annotate(
                value=Avg('value'),
                predicted_value=Avg('predicted_value'),
                lower_confidence_band=Avg('lower_confidence_band'),
                upper_confidence_band=Avg('upper_confidence_band'),
                anomaly_degree=Avg('anomaly_degree'),
            )
            .order_by('time')
        )
