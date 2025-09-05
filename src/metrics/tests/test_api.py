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


def get_metric_values_url(id):
    """Create and return the metric values URL."""
    return reverse('metrics:metric-values-list', args=[id])


def get_metric_time_dimensions_url(id):
    """Create and return the metric time dimensions URL."""
    return reverse('metrics:metric-time-dimensions-list', args=[id])


def get_metric_spatial_dimension_detail_url(id, h3_index):
    """Create and return the metric spatial dimension detail URL."""
    return reverse('metrics:metric-spatial-dimensions-detail', args=[id, h3_index])


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

    def test_retrieve_metric_value_metric_not_found(self, client):
        """
        Test the retrieval of a MetricValue instance that does not exist.
        """
        url = get_metric_values_url(999)
        res = client.get(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_metric_value_list_number_of_queries(self, metric_values, client, connection):
        """
        Retrieve the list of MetricValue instances and check the number of queries executed.
        """
        metric_to_test = metric_values[0].metric.id
        METRIC_VALUES_URL = get_metric_values_url(metric_to_test)
        res = client.get(METRIC_VALUES_URL)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data['results'][0]['value']
        # One query for results, one for checking the existence of metric and one for the count
        assert len(connection.queries) == 3


@pytest.mark.django_db(transaction=True)
class TestMetricTimeDimensionListView:
    """
    Test suite for the MetricTimeDimension list API.
    """

    def test_metric_time_dimensions_url(self, metrics):
        """
        Test the URL for the MetricTimeDimension list.
        """
        for metric in metrics:
            url = get_metric_time_dimensions_url(metric.id)
            assert url == f"/api/v2/metrics/{metric.id}/time_dimensions/"

    def test_retrieve_metric_time_dimension_list(self, client, metric_time_dimensions):
        """
        Retrieve a list of MetricTimeDimension instances.
        """
        metric_to_test = metric_time_dimensions[0].metric.id
        METRIC_TIME_DIMENSIONS_URL = get_metric_time_dimensions_url(metric_to_test)
        res = client.get(METRIC_TIME_DIMENSIONS_URL)

        metric_time_dimensions_from_db = models.MetricTimeDimension.objects.all()
        serialized = serializers.MetricTimeDimensionSerializer(metric_time_dimensions_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 2
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_time_dimension_filter_by_time_range(self, metric_time_dimensions, client):
        """
        Retrieve a list of MetricTimeDimension instances filtered by a time range.
        """
        metric_to_test = metric_time_dimensions[0].metric.id
        METRIC_TIME_DIMENSIONS_URL = get_metric_time_dimensions_url(metric_to_test)
        time = utils.time1
        res = client.get(METRIC_TIME_DIMENSIONS_URL, {'time_after': time, 'time_before': time})

        metric_time_dimensions_from_db = models.MetricTimeDimension.objects.filter(
            metric=metric_to_test,
            time__range=(time, time)
        )
        serialized = serializers.MetricTimeDimensionSerializer(metric_time_dimensions_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 1
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_time_dimension_filter_by_type(self, metric_time_dimensions, client):
        """
        Retrieve a list of MetricTimeDimension instances filtered by type.
        """
        metric_to_test = metric_time_dimensions[0].metric.id
        METRIC_TIME_DIMENSIONS_URL = get_metric_time_dimensions_url(metric_to_test)
        res = client.get(METRIC_TIME_DIMENSIONS_URL, {'type': 1})

        metric_time_dimensions_from_db = models.MetricTimeDimension.objects.filter(
            metric=metric_to_test,
            type=1
        )
        serialized = serializers.MetricTimeDimensionSerializer(metric_time_dimensions_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 1
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_time_dimensions_prediction_progress_gte(self, metric_time_dimensions, client):
        """
        Retrieve a list of MetricTimeDimension instances filtered by a certain level of prediction progress.
        """
        time_dimension_to_test = metric_time_dimensions[0]
        time_dimension_to_test.total_cells = 2
        time_dimension_to_test.total_cells_predicted = 2
        time_dimension_to_test.save()

        metric_to_test = time_dimension_to_test.metric.id
        METRIC_TIME_DIMENSIONS_URL = get_metric_time_dimensions_url(metric_to_test)
        res = client.get(METRIC_TIME_DIMENSIONS_URL, {'prediction_progress_gte': 0.8})

        metric_time_dimensions_from_db = models.MetricTimeDimension.objects.filter(
            metric=metric_to_test,
            prediction_progress__gte=0.8
        )
        serialized = serializers.MetricTimeDimensionSerializer(metric_time_dimensions_from_db, many=True)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 1
        for res_i in res.data['results']:
            assert res_i in serialized.data

    def test_retrieve_metric_time_dimension_metric_not_found(self, client):
        """
        Test the retrieval of a MetricTimeDimension instance that does not exist.
        """
        url = get_metric_time_dimensions_url(999)
        res = client.get(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_metric_time_dimension_list_number_of_queries(self, metric_time_dimensions, client, connection):
        """
        Retrieve the list of MetricTimeDimension instances and check the number of queries executed.
        """
        metric_to_test = metric_time_dimensions[0].metric.id
        METRIC_TIME_DIMENSIONS_URL = get_metric_time_dimensions_url(metric_to_test)
        res = client.get(METRIC_TIME_DIMENSIONS_URL)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data['results'][0]['time']
        # One query for results, one for checking the existence of metric and one for the count
        assert len(connection.queries) == 3


@pytest.mark.django_db(transaction=True)
class TestMetricSpatialDimensionRetrieveView:
    """
    Test suite for retrieving MetricSpatialDimension instances.
    """

    def test_metric_spatial_dimension_detail_url(self, metrics, metric_spatial_dimensions):
        """
        Test the detail URL for a specific MetricSpatialDimension instance.
        """
        metric_id = metrics[0].id
        h3_index = metric_spatial_dimensions[0].h3_index
        url = get_metric_spatial_dimension_detail_url(metric_id, h3_index)
        assert url == f"/api/v2/metrics/{metric_id}/spatial_dimensions/{h3_index}/"

    def test_retrieve_metric_spatial_dimension_detail(self, client, metric_spatial_dimensions):
        """
        Test the retrieval of a specific MetricSpatialDimension instance.
        """
        spatial_dimension_to_test = metric_spatial_dimensions[0]
        metric_id = spatial_dimension_to_test.metric.id
        h3_index = spatial_dimension_to_test.h3_index
        url = get_metric_spatial_dimension_detail_url(metric_id, h3_index)
        res = client.get(url)

        serialized = serializers.MetricSpatialDimensionSerializer(spatial_dimension_to_test)
        assert res.status_code == status.HTTP_200_OK
        assert res.data == serialized.data

    def test_retrieve_metric_spatial_dimension_metric_not_found(self, client):
        """
        Test the retrieval of a MetricSpatialDimension instance that does not exist.
        """
        url = get_metric_spatial_dimension_detail_url(999, 999)
        res = client.get(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_metric_spatial_dimension_not_found(self, client, metric_spatial_dimensions):
        """
        Test the retrieval of a MetricSpatialDimension instance that does not exist.
        """
        url = get_metric_spatial_dimension_detail_url(metric_spatial_dimensions[0].metric.id, 999)
        res = client.get(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_metric_spatial_dimension_number_of_queries(self, client, metric_spatial_dimensions, connection):
        """
        Test the number of queries executed when retrieving a MetricSpatialDimension instance.
        """
        url = get_metric_spatial_dimension_detail_url(
            metric_spatial_dimensions[0].metric.id, metric_spatial_dimensions[0].h3_index)
        res = client.get(url)

        assert res.status_code == status.HTTP_200_OK
        _ = res.data
        # One query for results and one for checking the existence of metric
        assert len(connection.queries) == 2


@pytest.mark.django_db(transaction=True)
class TestMetricValueBatchCreateView:
    """
    Test suite for creating MetricValue instances in bulk.
    """
    # TODO: Should I test this? Or maybe check first if the endpoint works for 3 million records?
