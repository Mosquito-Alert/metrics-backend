# myproject/filters.py
import django_filters as filters
from django import forms
from src.metrics import models
from utils.database_features import H3Field
import h3


class BaseH3FilterSet(filters.FilterSet):
    """Base filter set with H3Field treated as CharField globally."""

    class Meta:
        filter_overrides = {
            H3Field: {
                'filter_class': filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'exact',
                    'widget': forms.TextInput,
                },
            }
        }


class MetricValueFilter(BaseH3FilterSet):
    """
    Filter for MetricValue model.
    """
    h3_index = filters.CharFilter(field_name='h3_index', lookup_expr='exact',
                                  widget=forms.TextInput, label='H3 Index', required=False)
    lat = filters.NumberFilter(widget=forms.NumberInput, label='Latitude', required=False)
    long = filters.NumberFilter(widget=forms.NumberInput, label='Longitude', required=False)
    time = filters.IsoDateTimeFromToRangeFilter(
        field_name='time',
        label='Time Range',
        required=False,
    )
    type = filters.ChoiceFilter(
        field_name='type',
        choices=[(x.value, x.label) for x in models.MetricValue.MetricValueType],
        label='Type',
        required=False,
    )

    order_by = filters.OrderingFilter(
        fields=(('time', 'time'),),
        field_labels={'time': 'Time', },
        label='Order By',
        required=False,
    )

    def filter_queryset(self, queryset):
        """
        Enforce mutual exclusivity:
        - If h3_index is provided, ignore lat/long.
        - If lat & long are provided, convert to h3_index and filter.
        """
        h3_index = self.data.get('h3_index')
        lat = self.data.get('lat')
        long = self.data.get('long')

        if lat is not None and long is not None:
            try:
                # TODO: Find a better way to get metric_id
                metric_id = self.request.parser_context['kwargs']['metric_id']
                resolution = models.Metric.objects.get(
                    id=metric_id
                ).h3_resolution
                # TODO: Do it in database
                h3_index = h3.latlng_to_cell(
                    lat=float(lat),
                    lng=float(long),
                    res=resolution
                )
                self.data['h3_index'] = h3_index
                self.data.pop('lat', None)
                self.data.pop('long', None)
            except ValueError:
                return queryset.none()  # Invalid lat/long values
        if h3_index is not None:
            queryset = queryset.filter(h3_index=h3_index)

        return super().filter_queryset(queryset)

    class Meta(BaseH3FilterSet.Meta):
        model = models.MetricValue
        fields = ['h3_index', 'time', 'type']


class MetricStatisticsFilter(filters.FilterSet):
    """
    Filter for MetricStatistics model.
    """
    time = filters.IsoDateTimeFromToRangeFilter(
        field_name='time',
        label='Time Range',
        required=False,
    )
    prediction_progress_gte = filters.NumberFilter(
        field_name='prediction_progress_gte',
        lookup_expr='gte',
        label='Prediction Progress Greater Than or Equal',
        required=False,
    )

    order_by = filters.OrderingFilter(
        fields=(('time', 'time'),),
        field_labels={'time': 'Time', },
        label='Order By',
        required=False,
    )

    def filter_queryset(self, queryset):
        """
        Filter by metric_id.
        """
        metric_id = self.data.get('metric_id')
        if not metric_id:
            return queryset.none()

        return super().filter_queryset(queryset.filter(metric_id=metric_id))

    class Meta:
        model = models.MetricStatistics
        fields = ['time', 'prediction_progress_gte']
