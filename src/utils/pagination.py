from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """
    Custom pagination class for the API.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    page_query_param = 'page'

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        try:
            page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
        except ValueError:
            page_size = self.page_size

        if page_size == -1:
            self.page = None
            self.count = queryset.count()
            self.requested_page_size = page_size
            self.results = list(queryset)
            return self.results

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        if getattr(self, "requested_page_size", None) == -1:
            return Response({
                'count': self.count,
                'next': None,
                'previous': None,
                'results': data
            })
        return super().get_paginated_response(data)
