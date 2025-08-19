
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from src.metrics.models import Metric, PredictorConfig, MetricStatistics


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'is_predictable', 'h3_resolution', 'time_dimension_step')
    search_fields = ('name', 'code')
    list_filter = ('is_predictable', 'h3_resolution')
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('General'), {
            'fields': ['name', 'code', 'time_dimension_step', 'is_predictable', 'h3_resolution']
        }),
        (_('Dates'), {
            'fields': ['created_at', 'updated_at']
        }),
    )

# NOTE: "the Django admin. Models with composite primary keys cannot be registered in the Django admin at this
# time. You can expect to see this in future releases."
# https://docs.djangoproject.com/en/5.2/topics/composite-primary-key/
# @admin.register(MetricValue)
# class MetricValueAdmin(admin.ModelAdmin):
#     list_display = ('metric', 'h3_index', 'time', 'value', 'type')
#     search_fields = ('metric__name', 'h3_index')
#     list_filter = ('metric', 'type')
#     ordering = ['-metric', '-time', 'h3_index']
#     fieldsets = (
#         (_('General'), {
#             'fields': ['metric', 'h3_index', 'time', 'value', 'type']
#         }),
#         (_('Prediction'), {
#             'fields': ['predicted_value', 'lower_confidence_band', 'upper_confidence_band', 'anomaly_degree']
#         }),

#     )
#     readonly_fields = ['anomaly_degree']


@admin.register(PredictorConfig)
class PredictorConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'metric', 'yearly_seasonality', 'weekly_seasonality',
                    'daily_seasonality', 'growth',)
    search_fields = ('metric__name',)
    list_filter = ('metric', 'yearly_seasonality', 'weekly_seasonality', 'daily_seasonality', 'growth')
    ordering = ['-metric']
    fieldsets = (
        (_('General'), {
            'fields': ['metric', 'yearly_seasonality', 'weekly_seasonality',
                       'daily_seasonality', 'growth']
        }),
    )

# NOTE: Composite primary keys cannot be registered in the Django admin at this time.
# https://docs.djangoproject.com/en/5.2/topics/composite-primary-key/
# @admin.register(Predictor)
# class PredictorAdmin(admin.ModelAdmin):
#     list_display = ('metric', 'h3_index', 'last_training_date',)
#     search_fields = ('metric__name', 'h3_index')
#     list_filter = ('metric')
#     ordering = ['-last_training_date']
#     fieldsets = (
#         (_('General'), {
#             'fields': ['metric', 'h3_index', 'last_training_date', 'weights']
#         }),
#         (_('Predictions'), {
#             'fields': ['yearly_seasonality', 'weekly_seasonality', 'daily_seasonality', 'trend']
#         }),
#     )


@admin.register(MetricStatistics)
class MetricStatisticsAdmin(admin.ModelAdmin):
    list_display = ('metric', 'time', 'prediction_progress', )
    search_fields = ('metric__name', 'time')
    list_filter = ('metric',)
    ordering = ['-metric', '-time']
    fieldsets = (
        (_('General'), {
            'fields': ['metric', 'time', 'prediction_progress']
        }),
    )
