from rest_framework.routers import DefaultRouter

from src.tasks import views

router = DefaultRouter()
router.register(r'tasks', views.TasksViewSet, basename='tasks')

app_name = 'tasks'

urlpatterns = router.urls
