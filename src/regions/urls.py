

from rest_framework.routers import DefaultRouter

from src.regions import views

router = DefaultRouter()

router.register('regions', views.RegionViewSet, basename='regions')

app_name = 'regions'

urlpatterns = router.urls
