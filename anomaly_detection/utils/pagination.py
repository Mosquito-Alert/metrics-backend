from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Custom pagination class for the API.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    page_query_param = 'page'
