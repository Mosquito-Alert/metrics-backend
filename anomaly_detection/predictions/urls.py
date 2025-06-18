from django.urls import path
from rest_framework.routers import DefaultRouter

from anomaly_detection.predictions import views


router = DefaultRouter()

router.register('metrics', views.MetricViewSet, basename='metrics')

app_name = 'metrics'

urlpatterns = router.urls + [
    path('timeseries-json/', views.TileJSONView.as_view(), name='timeseries-json'),
]

# urlpatterns = [
# ...
#     views.CityAndStateTileView.get_url(),  # serve tiles at /city-and-states/<int:z>/<int:x>/<int:y>
#     views.CityAndStateTileJSON.get_urls(tiles_urls=views.CityAndStateTileView.get_url()),  # serve tilejson at /city-and-states/tiles.json
#     ...
# ]
