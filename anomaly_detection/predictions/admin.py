
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from anomaly_detection.predictions.models import Metric, MetricPredictionProgress, Predictor


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('id', 'region', 'date', 'anomaly_degree')
    search_fields = ('region__name', 'date', 'anomaly_degree')
    list_filter = ('date', 'region')
    ordering = ['-date']
    fieldsets = (
        (_('General'), {
            'fields': ['region', 'date', 'predictor']
        }),
        (_('Values'), {
            'fields': ['anomaly_degree', 'value', 'predicted_value', 'lower_value', 'upper_value']
        }),
        (_('Dates'), {
            'fields': ['created_at', 'updated_at']
        }),
    )
    readonly_fields = ['created_at', 'updated_at', 'anomaly_degree']


@admin.register(Predictor)
class PredictorAdmin(admin.ModelAdmin):
    list_display = ('id', 'region', 'last_training_date')
    search_fields = ['region__name']
    list_filter = ['region', 'last_training_date']
    ordering = ['-last_training_date']
    fieldsets = (
        (_('General'), {
            'fields': ['region', 'last_training_date', 'weights']
        }),
        (_('Predictions'), {
            'fields': ['yearly_seasonality', 'trend']
        }),
    )
    readonly_fields = ['yearly_seasonality', 'trend']


@admin.register(MetricPredictionProgress)
class MetricPredictionProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'success_percentage')
    list_filter = ['date']
    ordering = ['-date']
    fieldsets = (
        (_('General'), {
            'fields': ['date', 'success_percentage']
        }),
    )
