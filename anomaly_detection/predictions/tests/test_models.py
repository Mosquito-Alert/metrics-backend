import pytest

from anomaly_detection.regions.models import Municipality
from anomaly_detection.predictions.models import Metric, MetricExecution, MetricSeasonality


@pytest.mark.django_db
class TestMetricModel:
    """
    Test the Metric model.
    """

    def test_metric_creation(self, metrics, municipality):
        """
        Test the creation of a Metric instance.
        """
        municipality1, _ = municipality
        metric1, metric2, _, _ = metrics
        assert isinstance(metric1, Metric)
        assert metric1.region.code == 'ESP.1.1.1.1_1'
        assert metric2.date == '2023-01-02'
        assert metric1.region == municipality1

    def test_metric_str(self, metrics):
        """
        Test the string representation of a Metric instance.
        """
        metric1, _, _, _ = metrics
        assert str(metric1) == f"Bites Index Metric for {metric1.region.name} on {metric1.date}: {metric1.value}"

    def test_metric_meta(self):
        """
        Test the Meta class of the Metric model.
        """
        assert Metric._meta.verbose_name == 'Metric'
        assert Metric._meta.verbose_name_plural == 'Metrics'
        assert Metric._meta.ordering == ['region', '-date']
        assert Metric._meta.indexes[0].fields == ['date']
        assert Metric._meta.indexes[1].fields == ['region', 'date']
        assert Metric._meta.unique_together is not None

    def test_metric_anomaly_degree(self, metrics):
        """
        Test the anomaly degree calculation.
        """
        metric1, metric2, metric3, _ = metrics
        assert metric2.anomaly_degree is not None
        assert isinstance(metric2.anomaly_degree, float)
        assert metric1.anomaly_degree == 0.0
        assert metric2.anomaly_degree == (metric2.value - metric2.upper_value) / metric2.value
        assert metric3.anomaly_degree == (metric3.value - metric3.lower_value) / metric3.value

    def test_metric_region(self, metrics, multipolygon):
        """
        Test the region field of the Metric model.
        """
        metric1, _, _, _ = metrics
        assert metric1.region is not None
        assert isinstance(metric1.region, Municipality)
        assert metric1.region.code == 'ESP.1.1.1.1_1'
        assert metric1.region.name == 'Test Municipality'
        assert metric1.region.geometry == multipolygon

    def test_metric_region_geometry_deferred_by_default(self, metrics, connection):
        """
        Test that the geometry field is deferred by default.
        """
        # Get the first Metric instance
        metric1 = Metric.objects.first()

        # Accessing region should NOT trigger additional query
        _ = metric1.region
        queries_after_region = len(connection.queries)

        # Accessing geometry SHOULD trigger additional query (deferred)
        _ = metric1.region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_region == 1
        assert queries_after_geometry == 2

    def test_metric_region_with_geometry(self, metrics, connection):
        """
        Test that the region field with geometry is not deferred.
        """

        # Get the first Metric instance
        metric1 = Metric.objects.with_geometry().first()

        # Accessing region with geometry should NOT trigger additional query
        _ = metric1.region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_geometry == 1


@pytest.mark.django_db
class TestMetricSeasonalityModel:
    """
    Test the MetricSeasonality model.
    """

    def test_metric_seasonality_creation(self, seasonalities, municipality):
        """
        Test the creation of a MetricSeasonality instance.
        """
        municipality1, _ = municipality
        seasonality1, seasonality2, _ = seasonalities
        assert isinstance(seasonality1, MetricSeasonality)
        assert seasonality1.region.code == 'ESP.1.1.1.1_1'
        assert seasonality2.yearly_value == 0.6
        assert seasonality1.region == municipality1

    def test_metric_seasonality_str(self, seasonalities):
        """
        Test the string representation of a MetricSeasonality instance.
        """
        seasonality1, _, _ = seasonalities
        assert str(
            seasonality1) == (
                f"Bites Index Metric Seasonality for {seasonality1.region.name} on day {seasonality1.index + 1}: "
                f"{seasonality1.yearly_value}"
        )

    def test_metric_seasonality_meta(self):
        """
        Test the Meta class of the MetricSeasonality model.
        """
        assert MetricSeasonality._meta.verbose_name == 'Seasonality for metric'
        assert MetricSeasonality._meta.verbose_name_plural == 'Seasonalities for metric'
        assert MetricSeasonality._meta.ordering == ['region', 'index']
        assert MetricSeasonality._meta.indexes[0].fields == ['index']
        assert MetricSeasonality._meta.unique_together is not None

    def test_metric_seasonality_region(self, seasonalities, multipolygon):
        """
        Test the region field of the MetricSeasonality model.
        """
        seasonality1, _, _ = seasonalities
        assert seasonality1.region is not None
        assert isinstance(seasonality1.region, Municipality)
        assert seasonality1.region.code == 'ESP.1.1.1.1_1'
        assert seasonality1.region.name == 'Test Municipality'
        assert seasonality1.region.geometry == multipolygon

    def test_metric_seasonality_region_geometry_deferred_by_default(self, seasonalities, connection):
        """
        Test that the geometry field is deferred by default.
        """
        # Get the first MetricSeasonality instance
        seasonality1 = MetricSeasonality.objects.first()

        # Accessing region should NOT trigger additional query
        _ = seasonality1.region
        queries_after_region = len(connection.queries)

        # Accessing geometry SHOULD trigger additional query (deferred)
        _ = seasonality1.region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_region == 1
        assert queries_after_geometry == 2

    def test_metric_seasonality_region_with_geometry(self, seasonalities, connection):
        """
        Test that the region field with geometry is not deferred.
        """
        # Get the first MetricSeasonality instance
        seasonality1 = MetricSeasonality.objects.with_geometry().first()

        # Accessing region with geometry should NOT trigger additional query
        _ = seasonality1.region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_geometry == 1


@pytest.mark.django_db
class TestMetricExecution:
    """
    Test the MetricExecution model.
    """

    def test_metric_execution_creation(self, metric_executions):
        """
        Test the creation of a MetricExecution instance.
        """
        metric_execution1, metric_execution2, _ = metric_executions
        assert isinstance(metric_execution1, MetricExecution)
        assert metric_execution1.date == '2024-01-31'
        assert metric_execution1.success_percentage == 0.99
        assert metric_execution2.date == '2024-01-30'

    def test_metric_execution_str(self, metric_executions):
        """
        Test the string representation of a MetricExecution instance.
        """
        metric_execution1, _, _ = metric_executions
        assert str(
            metric_execution1) == (
                f"Metric Execution of the day {metric_execution1.date} with result: "
                f"{metric_execution1.success_percentage}"
        )
