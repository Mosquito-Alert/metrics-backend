

from src.metrics import routers, views


router = routers.SimpleRouter()
router.register('metrics', views.MetricViewSet, basename='metrics')

metrics_router = routers.NestedSimpleRouter(router, r'metrics', lookup='')
metrics_router.register('values', views.MetricViewSet.MetricValueViewSet, basename='metric-values')

metrics_router.register(
    'spatial_dimensions', views.MetricViewSet.MetricSpatialDimensionViewSet, basename='metric-spatial-dimensions')

metrics_router.register(
    'time_dimensions', views.MetricViewSet.MetricTimeDimensionViewSet, basename='metric-time-dimensions')

app_name = 'metrics'

urlpatterns = router.urls + metrics_router.urls
