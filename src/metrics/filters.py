# myproject/filters.py
from django.core.exceptions import BadRequest
import django_filters as filters
from django import forms
from src.metrics import models
import h3


class MetricValueFilter(filters.FilterSet):
    """
    Filter for MetricValue model.
    """
    h3_index = filters.CharFilter(field_name='h3_index', lookup_expr='exact',
                                  widget=forms.TextInput, label='H3 Index', required=False)
    # TODO: Implement bbox. Return all the metrics inside it.
    lat = filters.NumberFilter(widget=forms.NumberInput, label='Latitude', required=False, method='filter_lat_lng')
    lng = filters.NumberFilter(widget=forms.NumberInput, label='Longitude', required=False, method='filter_lat_lng')
    time = filters.IsoDateTimeFromToRangeFilter(
        field_name='time',
        label='Time Range',
        required=False,
    )

    order_by = filters.OrderingFilter(
        fields=(('time', 'time'),),
        field_labels={'time': 'Time', },
        label='Order By',
        required=False,
    )

    def filter_lat_lng(self, queryset, name, value):
        if value and (value < -180 or value > 180):
            raise BadRequest(f"Invalid value for {name}: {value}. Must be between -180 and 180.")
        return queryset

    def filter_queryset(self, queryset):
        """
        Enforce mutual exclusivity:
        - If h3_index is provided, ignore lat/lng.
        - If lat & lng are provided, convert to h3_index and filter.
        """
        data = self.data.copy()  # make a mutable copy
        h3_index = data.get('h3_index')
        lat = data.get('lat')
        lng = data.get('lng')

        if lat is not None and lng is not None:
            try:
                # TODO: Find a better way to get metric_id
                metric_id = self.request.parser_context['kwargs']['id']
                resolution = models.Metric.objects.get(
                    id=metric_id
                ).h3_resolution
                # TODO: Do it in database
                h3_index = h3.latlng_to_cell(
                    lat=float(lat),
                    lng=float(lng),
                    res=resolution
                )
                data['h3_index'] = h3_index
                data.pop('lat', None)
                data.pop('lng', None)
            except ValueError:
                return queryset.none()  # Invalid lat/lng values
        if h3_index is not None:
            queryset = queryset.filter(h3_index=h3_index)

        # Override self.data safely
        self.data = data

        return super().filter_queryset(queryset)

    class Meta:
        model = models.MetricValue
        fields = ['h3_index', 'time']


class MetricTimeDimensionFilter(filters.FilterSet):
    """
    Filter for MetricTimeDimension model.
    """
    time = filters.IsoDateTimeFromToRangeFilter(
        field_name='time',
        label='Time Range',
        required=False,
    )
    prediction_progress_gte = filters.NumberFilter(
        field_name='prediction_progress',
        lookup_expr='gte',
        label='Prediction Progress Greater Than or Equal',
        required=False,
    )
    type = filters.ChoiceFilter(
        field_name='type',
        choices=[(x.value, x.label) for x in models.MetricTimeDimension.MetricValueType],
        label='Type',
        required=False,
    )

    order_by = filters.OrderingFilter(
        fields=(('time', 'time'),),
        field_labels={'time': 'Time', },
        label='Order By',
        required=False,
    )

    class Meta:
        model = models.MetricTimeDimension
        fields = ['time', 'prediction_progress_gte', 'type']
