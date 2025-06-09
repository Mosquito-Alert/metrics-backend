from rest_framework.routers import DefaultRouter

from anomaly_detection.predictions import views


router = DefaultRouter()

router.register('metrics', views.MetricViewSet, basename='metrics')

app_name = 'metrics'

urlpatterns = router.urls
