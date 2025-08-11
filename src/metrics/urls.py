from rest_framework.routers import DefaultRouter

from src.metrics import views


router = DefaultRouter()

router.register('metrics', views.MetricViewSet, basename='metrics')

app_name = 'metrics'

urlpatterns = router.urls
