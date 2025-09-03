import h3
import pytest
from django.urls import reverse
from rest_framework import status

from src.metrics import models, serializers

from . import utils

METRICS_URL = reverse('metrics:metrics-list')


def get_metric_detail_url(id):
    """Create and return the metric detail URL."""
    return reverse('metrics:metrics-detail', args=[id])


def get_metric_values_url(metric_id):
    """Create and return the metric values URL."""
    return reverse('metrics:metric-values-list', args=[metric_id])


@pytest.mark.django_db(transaction=True)
class TestMetricListView:
    """
    Tests the Metric List View
    """

    def test_metrics_list_url(self, client):
        """
        Test that the reverse returns the correct URL for the metrics list view.
        """
        assert METRICS_URL == '/api/v2/metrics/'

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
        assert len(connection.queries) == 2


@pytest.mark.django_db(transaction=True)
class TestMetricDetailView:
    """
    Tests the Metric Detail View
    """

    def test_metric_detail_url(self, metrics):
        """
        Test that the reverse returns the correct URL for the metric detail view.
        """
        metric_to_test = metrics[0]
        assert get_metric_detail_url(metric_to_test.id) == f'/api/v2/metrics/{metric_to_test.id}/'

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
        assert len(connection.queries) == 1


@pytest.mark.django_db(transaction=True)
class TestMetricValueListView:
    """
    Tests the Metric Value List View
    """

    def test_metric_values_url(self, metrics):
        """
        Test that the reverse returns the correct URL for the metric values list view.
        """
        metric_to_test = metrics[0]
        assert get_metric_values_url(metric_to_test.id) == f'/api/v2/metrics/{metric_to_test.id}/values/'

    def test_retrieve_metric_value_list(self, client, metrics, metric_values):
        """
        Retrieve a list of MetricValue instances
        """
        metric_to_test = metrics[0]
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test.id)
        res = client.get(METRIC_VALUES_URL)

        metric_values_from_db = models.MetricValue.objects.filter(metric=metric_to_test)
        serialized = serializers.MetricValueSerializer(metric_values_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 4
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_value_list_filter_by_h3(self, metric_values, client):
        """
        Test filtering the MetricValue list by H3 index.
        """
        metric_to_test = metric_values[0].metric.id
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test)
        h3_index = utils.h3_index1
        res = client.get(METRIC_VALUES_URL, {'h3_index': h3_index})

        metric_values_from_db = models.MetricValue.objects.filter(metric=metric_to_test, h3_index=h3_index)
        serialized = serializers.MetricValueSerializer(metric_values_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 2
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_value_list_filter_by_time_range(self, metric_values, client):
        """
        Test filtering the MetricValue list by time.
        """
        metric_to_test = metric_values[0].metric.id
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test)
        time = utils.time1
        res = client.get(METRIC_VALUES_URL, {'time_after': time, 'time_before': time})

        metric_values_from_db = models.MetricValue.objects.filter(metric=metric_to_test, time__range=(time, time))
        serialized = serializers.MetricValueSerializer(metric_values_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 2
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_value_list_filter_by_lat_long(self, metric_values, client):
        """
        Test filtering the MetricValue list by latitude and longitude.
        """
        metric_to_test = metric_values[0].metric.id
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test)
        lat, lng = h3.cell_to_latlng(utils.h3_index1)
        res = client.get(METRIC_VALUES_URL, {'lat': lat, 'lng': lng})

        metric_values_from_db = models.MetricValue.objects.filter(metric=metric_to_test, h3_index=utils.h3_index1)
        serialized = serializers.MetricValueSerializer(metric_values_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 2
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_value_list_number_of_queries(self, metric_values, client, connection):
        """
        Retrieve the list of MetricValue instances and check the number of queries executed.
        """
        metric_to_test = metric_values[0].metric.id
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test)
        res = client.get(METRIC_VALUES_URL)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data['results'][1]['value']
        # One query for results and one for the count
        assert len(connection.queries) == 2
