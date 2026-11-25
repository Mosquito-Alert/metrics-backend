import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.urls import reverse


@pytest.mark.django_db
class TestTasksViewSet:
    @pytest.fixture
    def client(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="test", password="pass"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @patch("src.tasks.views.AsyncResult")
    def test_status_endpoint(self, mock_async_result, client):
        # Arrange
        fake_result = MagicMock()
        fake_result.status = "SUCCESS"
        fake_result.ready.return_value = True
        fake_result.successful.return_value = True
        mock_async_result.return_value = fake_result

        task_id = "1234"
        url = reverse("tasks:tasks-task-status", kwargs={"id": task_id})

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "task_id": task_id,
            "status": "SUCCESS",
            "ready": True,
            "successful": True,
        }

        mock_async_result.assert_called_once_with(task_id, app=mock_async_result.call_args[1]["app"])
