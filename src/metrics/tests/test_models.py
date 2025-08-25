import pytest

from src.metrics.models import Metric, PredictorConfig


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
        assert PredictorConfig.objects.filter(id=config1.id).count
