import pytest
from django.urls import reverse
from rest_framework import status

from src.metrics import models, serializers

METRICS_URL = reverse('metrics:metrics-list')


def get_metric_detail_url(id):
    """Create and return the metric detail URL."""
    return reverse('metrics:metrics-detail', args=[id])


# TODO: Don't install silk in test
def _get_queries(connection):
    """
    Filter the queries to get only the ones that contain 'SELECT' and 'metric'.
    """
    return [
        query for query in connection.queries
        if 'SELECT' in query['sql']
        and 'metric' in query['sql']
        and not query['sql'].startswith('EXPLAIN')
        and 'silk' not in query['sql']
    ]


@pytest.mark.django_db(transaction=True)
class TestMetricListView:
    """
    Tests the Metric List View
    """

    def test_retrieve_metrics_list(self, client, metrics):
        """
        Retrieve a list of Metric instances
        """
        res = client.get(METRICS_URL)

        metrics_from_db = models.Metric.objects.all()
        serialized = serializers.MetricListSerializer(metrics_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 2
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_list_number_of_queries(self, metrics, client, connection):
        """
        Retrieve the list of Metric instances and check the number of queries executed.
        """

        res = client.get(METRICS_URL)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data['results'][1]['code']
        # One query for results and one for the count
        assert len(_get_queries(connection)) == 2


@pytest.mark.django_db(transaction=True)
class TestMetricDetailView:
    """
    Tests the Metric Detail View
    """

    def test_retrieve_metric_detail(self, client, metrics):
        """
        Retrieve a single Metric instance
        """
        metric_to_test = metrics[0]
        url = get_metric_detail_url(metric_to_test.id)
        res = client.get(url)

        serialized = serializers.MetricSerializer(metric_to_test)
        assert res.status_code == status.HTTP_200_OK
        assert res.data == serialized.data
        # Check that the time_dimension_step is a valid string of the enum
        assert res.data['time_dimension_step'] in [
            x.name.lower() for x in models.Metric.TimeDimensionStepType
        ]

    def test_retrieve_metric_detail_not_found(self, client):
        """
        Attempt to retrieve a Metric instance that does not exist
        """
        url = get_metric_detail_url(999)
        res = client.get(url)

        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_metric_detail_number_of_queries(self, metrics, client, connection):
        """
        Retrieve the detail of a Metric instance and check the number of queries executed.
        """
        metric_to_test = metrics[0]
        url = get_metric_detail_url(metric_to_test.id)
        res = client.get(url)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data['code']
        assert len(_get_queries(connection)) == 1
