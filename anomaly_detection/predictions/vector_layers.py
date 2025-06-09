from vectortiles import VectorLayer

from .models import Metric


class MetricMunicipalityVectorLayer(VectorLayer):
    queryset = Metric.objects.with_geometry()
    id = "metrics"
    tile_fields = ('anomaly_degree', 'id', 'region__name',)
    min_zoom = 0
    geom_field = "region__geometry"

    def __init__(self, date, *args, **kwargs):
        if date is None:
            raise ValueError("Date is mandatory.")
        self.date = date
        super().__init__(*args, **kwargs)

    def get_vector_tile_queryset(self, *args, **kwargs):
        """
        Override the default get_vector_tile_queryset to filter by date.
        """
        return super().get_vector_tile_queryset(*args, **kwargs).filter(date=self.date).order_by()
