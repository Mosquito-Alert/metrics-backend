from datetime import datetime, timezone
from django.db import IntegrityError
import pytest
from django.core.exceptions import ValidationError

from src.metrics.models import Metric, MetricStatistics, MetricValue, PredictorConfig
from . import utils


@pytest.mark.django_db
class TestMetricModel:
    """
    Test the Metric model.
    """

    def test_metric_creation(self, metrics):
        """
        Test the creation of a Metric instance.
        """
        metric1, _ = metrics
        assert isinstance(metric1, Metric)
        assert metric1.code == 'metric_1'
        assert metric1.h3_resolution == 6

    def test_metric_meta(self):
        """
        Test the Meta class of the Metric model.
        """
        assert Metric._meta.verbose_name == 'Metric'
        assert Metric._meta.verbose_name_plural == 'Metrics'
        assert Metric._meta.ordering == ['-created_at']


@pytest.mark.django_db
class TestPredictorConfig:
    """
    Test the PredictorConfig model.
    """

    def test_predictor_config_creation(self, predictor_configs):
        """
        Test the creation of a PredictorConfig instance.
        """
        config1, _ = predictor_configs
        assert isinstance(config1, PredictorConfig)
        assert config1.growth == 'linear'
        assert config1.yearly_seasonality is True
        assert config1.metric.code == 'metric_1'

    def test_predictor_config_meta(self):
        """
        Test the Meta class of the PredictorConfig model.
        """
        assert PredictorConfig._meta.verbose_name == 'Predictor Config'
        assert PredictorConfig._meta.verbose_name_plural == 'Predictor Configs'

    def test_cascade_deletion_predictor_config(self, metrics, predictor_configs):
        """
        Test the deletion of a Predictor Config instance by cascade.
        """
        metric1, _ = metrics
        config1, _ = predictor_configs

        # Ensure the Metric is associated with the PredictorConfig
        assert metric1 == config1.metric

        # Delete the Metric
        metric1.delete()

        # Ensure the Predictor Config is deleted
        assert PredictorConfig.objects.filter(id=config1.id).count() == 0


@pytest.mark.django_db
class TestMetricValue:
    """
    Test the MetricValue model.
    """

    def test_metric_value_creation(self, metric_values):
        """
        Test the creation of a MetricValue instance.
        """
        value1, _, _, _, _ = metric_values
        assert isinstance(value1, MetricValue)
        assert value1.metric.code == 'metric_1'
        assert value1.h3_index == "860123507ffffff"
        assert value1.time == datetime.strptime('2025-01-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)
        assert value1.value == 0.123

    def test_metric_value_meta(self):
        """
        Test the Meta class of the MetricValue model.
        """
        assert MetricValue._meta.verbose_name == 'Metric Value'
        assert MetricValue._meta.verbose_name_plural == 'Metric Values'
        assert MetricValue._meta.ordering == ['metric', 'h3_index', '-time']
        assert len(MetricValue._meta.constraints) == 3
        assert MetricValue._meta.indexes[0].fields == ['metric', 'h3_index', 'time']

    # * Test H3 Index
    def test_metric_value_invalid_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with invalid h3 index.
        """
        metric1, _ = metrics
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                metric=metric1,
                h3_index="000000000000000",  # Invalid H3 index
                time=utils.time1,
                value=0.123,
            )

    def test_metric_value_non_hexadecimal_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with not an hexadecimal h3 index.
        """
        _, metric2 = metrics
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                metric=metric2,
                h3_index=603502369715519487,  # Non hexadecimal valid h3 index
                time=utils.time1,
                value=0.123,
            )

    def test_metric_value_invalid_resolution_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with invalid resolution h3 index.
        """
        metric1, _ = metrics
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                metric=metric1,
                h3_index=utils.h3_index_lvl8,  # Valid h3 index but invalid resolution
                time=utils.time1,
                value=0.123,
            )

    # * Test Predictable
    def test_metric_value_predictable_false(self, metric_values):
        """
        Test the behavior of MetricValue when is_predictable is False.
        """
        _, _, _, _, value5 = metric_values
        assert value5.metric.is_predictable is False
        assert value5.predicted_value is None
        assert value5.anomaly_degree is None

    def test_metric_value_and_predicted_value_false(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with value and predicted_value nulls.
        """
        _, metric2 = metrics
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                metric=metric2,
                h3_index=utils.h3_index_lvl8,
                time=utils.time1,
                value=None,
            )

    # * Test Time Rounding
    def test_metric_value_time_rounding(self, metrics):
        """
        Test the rounding of time in MetricValue.
        """
        _, metric2 = metrics
        value = MetricValue.objects.create(
            metric=metric2,
            h3_index=utils.h3_index_lvl8,
            time=datetime.strptime('2025-01-01T12:34:56Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),
            value=0.123,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        assert value.time == datetime.strptime('2025-01-01T12', '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)

    def test_metric_value_time_rounding_update(self, metric_values):
        """
        Test the rounding of time in MetricValue when an update is performed (model save method)
        """
        value1, _, _, _, _ = metric_values
        value1.time = datetime.strptime('2025-01-01T12:34:56Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        value1.save()
        assert value1.time == datetime.strptime('2025-01-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)

    # * Test Anomaly Degree
    def test_metric_value_anomaly_degree_zero_value(self, metrics):
        """
        Test calculate_anomaly_degree when value is zero.
        """
        metric1, _ = metrics
        # Case: upper_confidence_band < 0
        value = MetricValue.objects.create(
            metric=metric1,
            h3_index=utils.h3_index1,
            time=utils.time1,
            value=0.0,
            upper_confidence_band=-1.0,
            lower_confidence_band=0.0,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        assert value.anomaly_degree == 1.0

        # Case: lower_confidence_band > 0
        value.lower_confidence_band = 1.0
        value.upper_confidence_band = 0.0
        value.save()
        assert value.anomaly_degree == -1.0

        # Case: confidence bands include zero
        value.lower_confidence_band = -1.0
        value.upper_confidence_band = 1.0
        value.save()
        assert value.anomaly_degree == 0.0

    def test_metric_value_anomaly_degree_above_upper(self, metrics):
        """
        Test calculate_anomaly_degree when value is above upper confidence band.
        """
        metric1, _ = metrics
        value = MetricValue.objects.create(
            metric=metric1,
            h3_index=utils.h3_index1,
            time=utils.time1,
            value=10.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        expected = (10.0 - 8.0) / 10.0
        assert value.anomaly_degree == expected

    def test_metric_value_anomaly_degree_below_lower(self, metrics):
        """
        Test calculate_anomaly_degree when value is below lower confidence band.
        """
        metric1, _ = metrics
        value = MetricValue.objects.create(
            metric=metric1,
            h3_index=utils.h3_index1,
            time=utils.time1,
            value=1.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        expected = (1.0 - 2.0) / 1.0
        assert value.anomaly_degree == expected

    def test_metric_value_anomaly_degree_within_bands(self, metrics):
        """
        Test calculate_anomaly_degree when value is within confidence bands.
        """
        metric1, _ = metrics
        value = MetricValue.objects.create(
            metric=metric1,
            h3_index=utils.h3_index1,
            time=utils.time1,
            value=5.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        assert value.anomaly_degree == 0.0

    def test_metric_value_anomaly_degree_none_value(self, metrics):
        """
        Test calculate_anomaly_degree when value is None.
        """
        metric1, _ = metrics
        value = MetricValue.objects.create(
            metric=metric1,
            h3_index=utils.h3_index1,
            time=utils.time1,
            value=None,
            predicted_value=0.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
            type=MetricValue.MetricValueType.REANALYSIS
        )
        assert value.anomaly_degree is None

    # * Others

    def test_duplicate_key(self, metrics, metric_values):
        """
        Test the behavior of unique constraint when trying to create a duplicate MetricValue.
        """
        metric1, _ = metrics
        with pytest.raises(IntegrityError):
            MetricValue.objects.create(
                metric=metric1,
                h3_index=utils.h3_index1,
                time=utils.time1,
                value=0.456,
                type=MetricValue.MetricValueType.REANALYSIS
            )

    def test_create_metric_statistics(self,  metric_values):
        """
        Test the creation automatic of a MetricStatistics instance when a value is created.
        """
        value1, _, _, _, _ = metric_values
        stats = MetricStatistics.objects.filter(
            metric=value1.metric,
            time=value1.time
        )
        assert stats.exists()
