from rest_framework_nested import routers

from src.metrics import views


router = routers.SimpleRouter()
router.register('metrics', views.MetricViewSet, basename='metrics')

metrics_router = routers.NestedSimpleRouter(router, r'metrics', lookup='metric')
metrics_router.register('values', views.MetricValueViewSet, basename='metric-values')

metrics_router.register(
    'spatial_dimensions', views.MetricSpatialDimensionViewSet, basename='metric-spatial-dimensions')

metrics_router.register(
    'time_dimensions', views.MetricTimeDimensionViewSet, basename='metric-time-dimensions')

app_name = 'metrics'

urlpatterns = router.urls + metrics_router.urls
