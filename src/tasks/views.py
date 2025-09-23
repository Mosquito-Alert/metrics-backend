from celery.result import AsyncResult

from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from project.celery import app


class TasksViewSet(viewsets.ViewSet):
    """
    Views for tasks app.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "id"
    lookup_field = "id"

    @action(
        methods=['GET'],
        detail=True,
        url_name='task-status',
        url_path='status'
    )
    def status(self, request, *args, **kwargs):
        """
        Action that checks the status of a batch creation task.
        """
        id = kwargs.get('id')

        result = AsyncResult(id, app=app)
        return Response({
            "task_id": id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful(),
        })
