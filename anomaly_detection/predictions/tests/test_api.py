

import pytest
from django.urls import reverse
from rest_framework import status

from anomaly_detection.predictions.models import Metric, MetricSeasonality
from anomaly_detection.predictions.serializers import MetricSeasonalitySerializer, MetricSerializer


METRICS_URL = reverse('metrics:metrics-list')
METRICS_LAST_DATE_URL = reverse('metrics:metrics-last-date')
METRICS_SEASONALITY_URL = reverse('metrics:metrics-seasonality')


def get_metric_detail_url(id):
    """Create and return the metric detail URL."""
    return reverse('metrics:metrics-detail', args=[id])


def get_tiles_url(x, y, z):
    """Create and return the tiles URL."""
    return reverse('metrics:metrics-tiles', args=[z, x, y])


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
    Tests the Metric View for the List action.
    """

    def test_retrieve_metric_list(self, metrics, client):
        """
        Retrieve the list of Metric instances.
        """
        res = client.get(METRICS_URL)

        metrics_from_db = Metric.objects.all()
        serialized = MetricSerializer(metrics_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 4
        assert res.data[3]['value'] == metrics[3].value
        assert res.data[3]['region_code'] == metrics[3].region.code
        for res_i in res.data:
            assert res_i in serialized.data

    def test_retrieve_metric_list_history(self, metrics, client):
        """
        Retrieve the list of Metric instances for a specific Region (history mode).
        """

        res = client.get(METRICS_URL, {'region_code': 'ESP.1.1.1.1_1'})

        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 3

    def test_retrieve_metric_list_date(self, metrics, client):
        """
        Retrieve the list of Metric instances for a specific range of dates.
        """
        res = client.get(METRICS_URL, {'date_from': '2023-01-01', 'date_to': '2023-01-02'})

        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 2

    def test_retrieve_metric_list_number_of_queries(self, metrics, client, connection):
        """
        Retrieve the list of Metric instances and check the number of queries executed.
        """

        res = client.get(METRICS_URL)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data[1]['value']
        _ = res.data[1]['region_code']
        assert len(_get_queries(connection)) == 1


@pytest.mark.django_db(transaction=True)
class TestMetricTilesView:
    def test_retrieve_metric_tiles(self, metrics, client):
        """
        Retrieve the list of tiles of every municipality.
        """
        url = get_tiles_url(0, 0, 1)
        res = client.get(url, {'date': '2023-01-01'})

        assert res.status_code == status.HTTP_200_OK
        assert res.headers['Content-Type'] == 'application/vnd.mapbox-vector-tile; charset=utf-8'

    def test_retrieve_metric_tiles_number_of_queries(self, metrics, client, connection):
        """
        Retrieve the list of tiles of every municipality and check the number of queries executed.
        """
        url = get_tiles_url(0, 0, 1)
        res = client.get(url, {'date': '2023-01-01'})

        assert res.status_code == status.HTTP_200_OK
        assert len(_get_queries(connection)) == 1

    def test_retrieve_metric_tiles_empty(self, metrics, client):
        """
        Retrieve the list of tiles of every municipality, but out of focus.
        """
        url = get_tiles_url(250, 250, 5)
        res = client.get(url, {'date': '2023-01-01'})

        assert res.status_code == status.HTTP_204_NO_CONTENT

    def test_retrieve_metric_tiles_bad_request(self, client):
        """
        Test that checks that the query param 'date' is mandatory.
        """
        url = get_tiles_url(0, 0, 1)
        res = client.get(url)

        assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
class TestMetricDetailView:
    def test_retrieve_metric_detail(self, metrics, client):
        """
        Retrieve a single metric.
        """
        metric_id = metrics[0].id
        url = get_metric_detail_url(metric_id)
        res = client.get(url)

        assert res.status_code == status.HTTP_200_OK
        assert res.data['value'] == metrics[0].value
        assert res.data['region']['code'] == metrics[0].region.code
        assert 'geometry' not in res.data['region']

    def test_retrieve_metric_detail_number_of_queries(self, metrics, client, connection):
        """
        RRetrieve a single metric and check the number of queries executed.
        """
        metric_id = metrics[0].id
        url = get_metric_detail_url(metric_id)
        res = client.get(url)

        assert res.status_code == status.HTTP_200_OK
        assert len(_get_queries(connection)) == 1

    def test_retrieve_metric_detail_not_found(self, client):
        """
        Test that checks the not found error.
        """
        url = get_metric_detail_url('not_existing_id')
        res = client.get(url)

        assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
class TestDateMetricView:
    def test_retrieve_metric_date(self, metric_executions, client):
        """
        Retrieve the last date available.
        """
        metric_execution1, _, _ = metric_executions

        res = client.get(METRICS_LAST_DATE_URL)

        assert res.status_code == status.HTTP_200_OK
        assert res.data['date'] == metric_execution1.date

    def test_retrieve_metric_date_not_found(self, client):
        """
        Test that checks the not found error.
        """
        res = client.get(METRICS_LAST_DATE_URL)

        assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
class TestMetricSeasonalityView:
    def test_retrieve_seasonality(self, seasonalities, client):
        """
        Retrieve the seasonality for a specific region.
        """
        region_code = seasonalities[0].region.code
        res = client.get(METRICS_SEASONALITY_URL, {'region_code': region_code})

        seasonality_from_db = MetricSeasonality.objects.filter(region__code=region_code)
        serialized = MetricSeasonalitySerializer(seasonality_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 2
        for res_i in res.data:
            assert res_i in serialized.data

    def test_retrieve_seasonality_bad_request(self, client):
        """
        Test that checks that the query param 'region_code' is mandatory.
        """
        res = client.get(METRICS_SEASONALITY_URL)

        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_seasonality_not_found(self, client):
        """
        Test that checks the not found error.
        """
        res = client.get(METRICS_SEASONALITY_URL, {'region_code': 'not_existing_id'})

        assert res.status_code == status.HTTP_404_NOT_FOUND
