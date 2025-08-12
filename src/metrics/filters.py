# myproject/filters.py
import django_filters as filters
from django import forms
from src.metrics import models
from utils.database_features import H3Field


class MetricValueFilter(filters.FilterSet):
    """
    Filter for MetricValue model.
    """
    h3_index = filters.CharFilter(field_name='h3_index', lookup_expr='exact', widget=forms.TextInput)
    time = filters.IsoDateTimeFromToRangeFilter(
        field_name='time',
        label='Time Range'
    )
    type = filters.ChoiceFilter(
        field_name='type',
        choices=[(x.value, x.label) for x in models.MetricValue.MetricValueType],
        label='Type',
    )

    class Meta:
        model = models.MetricValue
        fields = ['h3_index', 'time', 'type']
        filter_overrides = {
            H3Field: {
                'filter_class': filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'exact',
                    'widget': forms.TextInput,
                },
            }
        }
