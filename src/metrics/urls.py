from rest_framework_nested import routers

from src.metrics import views


router = routers.SimpleRouter()
router.register('metrics', views.MetricViewSet, basename='metrics')

metric_values_router = routers.NestedSimpleRouter(router, r'metrics', lookup='metric')
metric_values_router.register('values', views.MetricValueViewSet, basename='metric-values')

app_name = 'metrics'

urlpatterns = router.urls + metric_values_router.urls
