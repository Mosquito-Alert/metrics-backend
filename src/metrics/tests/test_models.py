from datetime import datetime, timezone
from django.db import IntegrityError
import pytest
from django.core.exceptions import ValidationError

from src.metrics.models import Metric, MetricSpatialDimension, MetricTimeDimension, MetricValue, PredictorConfig
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

    def test_metric_value_creation(self, metric_values, metric_spatial_dimensions, metric_time_dimensions):
        """
        Test the creation of a MetricValue instance.
        """
        value1, _, _, _ = metric_values
        spatial_dimension1, _, _ = metric_spatial_dimensions
        time_dimension1, _, _ = metric_time_dimensions

        assert isinstance(value1, MetricValue)
        assert value1.spatial_dimension == spatial_dimension1
        assert value1.time_dimension == time_dimension1
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

    def test_metric_value_cannot_create_without_dimensions(self, metrics):
        """
        Test the behavior of validation error when trying to create metric without dimensions.
        """
        metric1, _ = metrics
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                metric=metric1,
                h3_index=utils.h3_index1,
                time=utils.time1,
                value=0.123,
            )

    def test_metric_value_cannot_create_with_different_metric(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test that when provided dimensions whose metric don't match, a validation error is raised.
        """
        time_dimension1, _, _ = metric_time_dimensions
        _, _, spatial_dimension3 = metric_spatial_dimensions
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                time_dimension=time_dimension1,
                spatial_dimension=spatial_dimension3,
                value=0.123,
            )

    # * Test Predictable
    def test_metric_value_predictable_false(self, metric_values):
        """
        Test the behavior of MetricValue when is_predictable is False.
        """
        _, _, _, value4 = metric_values
        assert value4.metric.is_predictable is False
        assert value4.predicted_value is None
        assert value4.anomaly_degree is None

    def test_metric_value_and_predicted_value_false(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test the behavior of validation error when trying to create metric with value and predicted_value nulls.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        with pytest.raises(ValidationError):
            MetricValue.objects.create(
                time_dimension=time_dimension1,
                spatial_dimension=spatial_dimension1,
                value=None,
            )

    # * Test Time Rounding
    def test_metric_value_time_rounding(self, metric_spatial_dimensions):
        """
        Test the rounding of time in MetricValue.
        """
        _, _, spatial_dimension3 = metric_spatial_dimensions
        time_dimension = MetricTimeDimension.objects.create(
            metric=spatial_dimension3.metric,
            time=datetime.strptime('2025-01-01T12:34:56Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),
            type=MetricTimeDimension.MetricValueType.REANALYSIS
        )
        value = MetricValue.objects.create(
            time_dimension=time_dimension,
            spatial_dimension=spatial_dimension3,
            value=0.123,
        )
        assert value.time == datetime.strptime('2025-01-01T12', '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)

    def test_metric_value_time_rounding_update(self, metric_values):
        """
        Test the rounding of time in MetricValue when an update is performed (model save method)
        """
        value1, _, _, _ = metric_values
        value1.time = datetime.strptime('2025-01-01T12:34:56Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        value1.save()
        assert value1.time == datetime.strptime('2025-01-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)

    # * Test Anomaly Degree
    def test_metric_value_anomaly_degree_zero_value(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test calculate_anomaly_degree when value is zero.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        # Case: upper_confidence_band < 0
        value = MetricValue.objects.create(
            time_dimension=time_dimension1,
            spatial_dimension=spatial_dimension1,
            value=0.0,
            upper_confidence_band=-1.0,
            lower_confidence_band=0.0,
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

    def test_metric_value_anomaly_degree_above_upper(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test calculate_anomaly_degree when value is above upper confidence band.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        value = MetricValue.objects.create(
            time_dimension=time_dimension1,
            spatial_dimension=spatial_dimension1,
            value=10.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
        )
        expected = (10.0 - 8.0) / 10.0
        assert value.anomaly_degree == expected

    def test_metric_value_anomaly_degree_below_lower(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test calculate_anomaly_degree when value is below lower confidence band.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        value = MetricValue.objects.create(
            time_dimension=time_dimension1,
            spatial_dimension=spatial_dimension1,
            value=1.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
        )
        expected = (1.0 - 2.0) / 1.0
        assert value.anomaly_degree == expected

    def test_metric_value_anomaly_degree_within_bands(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test calculate_anomaly_degree when value is within confidence bands.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        value = MetricValue.objects.create(
            time_dimension=time_dimension1,
            spatial_dimension=spatial_dimension1,
            value=5.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
        )
        assert value.anomaly_degree == 0.0

    def test_metric_value_anomaly_degree_none_value(self, metric_time_dimensions, metric_spatial_dimensions):
        """
        Test calculate_anomaly_degree when value is None.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        value = MetricValue.objects.create(
            time_dimension=time_dimension1,
            spatial_dimension=spatial_dimension1,
            value=None,
            predicted_value=0.0,
            upper_confidence_band=8.0,
            lower_confidence_band=2.0,
        )
        assert value.anomaly_degree is None

    # * Others
    def test_duplicate_key(self, metric_time_dimensions, metric_spatial_dimensions, metric_values):
        """
        Test the behavior of unique constraint when trying to create a duplicate MetricValue.
        """
        time_dimension1, _, _ = metric_time_dimensions
        spatial_dimension1, _, _ = metric_spatial_dimensions
        with pytest.raises(IntegrityError):
            MetricValue.objects.create(
                time_dimension=time_dimension1,
                spatial_dimension=spatial_dimension1,
                value=0.456,
            )


@pytest.mark.django_db
class TestMetricTimeDimension:
    """
    Test the MetricTimeDimension model.
    """

    def test_create_metric_time_dimension(self,  metric_time_dimensions):
        """
        Test the creation automatic of a MetricTimeDimension instance when a value is created.
        """
        time_dimension1, _, _ = metric_time_dimensions
        assert isinstance(time_dimension1, MetricTimeDimension)
        assert time_dimension1.metric.code == 'metric_1'
        assert time_dimension1.time == datetime.strptime('2025-01-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)
        assert time_dimension1.total_cells_completed is None
        assert time_dimension1.prediction_progress is None

    def test_metric_time_dimension_meta(self):
        """
        Test the Meta class of the MetricTimeDimension model.
        """
        assert MetricTimeDimension._meta.verbose_name == 'Metric Time Dimension'
        assert MetricTimeDimension._meta.verbose_name_plural == 'Metric Time Dimensions'
        assert MetricTimeDimension._meta.ordering == ['metric', '-time']
        assert len(MetricTimeDimension._meta.constraints) == 1
        assert MetricTimeDimension._meta.indexes[0].fields == ['metric', 'time']

    def test_increase_total_cells(self, metric_time_dimensions):
        """
        Test the increase of total_cells when the method is invoked.
        Also, assert that the prediction_progress is correctly updated.
        """
        time_dimension1, _, _ = metric_time_dimensions
        time_dimension1.total_cells = 3
        time_dimension1.save()

        time_dimension1.increase_total_cells(inc_value=2)
        time_dimension1.refresh_from_db()

        assert time_dimension1.total_cells == 5

    def test_increase_total_cells_completed(self, metric_time_dimensions):
        """
        Test the increase of total_cells_completed when the method is invoked.
        Also, assert that the prediction_progress is correctly updated.
        """
        time_dimension1, _, _ = metric_time_dimensions
        time_dimension1.total_cells = 3
        time_dimension1.total_cells_completed = 0
        time_dimension1.save()

        time_dimension1.increase_total_cells_completed(inc_value=2)
        time_dimension1.refresh_from_db()

        assert time_dimension1.total_cells_completed == 2
        assert round(time_dimension1.prediction_progress, 4) == 0.6667

    def test_metric_time_dimensions_total_cells(self, metric_values):
        """
        Test that the total cells field is calculated correctly at creation.
        """
        metric_value1, _, _, _ = metric_values
        stats = MetricTimeDimension.objects.get(
            metric=metric_value1.metric,
            time=metric_value1.time
        )

        assert stats.total_cells == 2


@pytest.mark.django_db
class TestMetricSpatialDimension:
    """
    Test the MetricSpatialDimension model.
    """

    def test_create_metric_spatial_dimension(self, metric_spatial_dimensions):
        """
        Test the creation automatic of a MetricSpatialDimension instance when a value is created.
        """
        spatial_dimension1, _, _ = metric_spatial_dimensions
        assert isinstance(spatial_dimension1, MetricSpatialDimension)
        assert spatial_dimension1.metric.code == 'metric_1'
        assert spatial_dimension1.h3_index == utils.h3_index1
        assert spatial_dimension1.trend is None

    def test_metric_spatial_dimension_meta(self):
        """
        Test the Meta class of the MetricSpatialDimension model.
        """
        assert MetricSpatialDimension._meta.verbose_name == 'Metric Spatial Dimension'
        assert MetricSpatialDimension._meta.verbose_name_plural == 'Metric Spatial Dimensions'
        assert MetricSpatialDimension._meta.ordering == ['metric', 'h3_index']
        assert len(MetricSpatialDimension._meta.constraints) == 2
        assert MetricSpatialDimension._meta.indexes[0].fields == ['metric', 'h3_index']

    # * Test H3 Index
    def test_metric_spatial_dimension_invalid_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with invalid h3 index.
        """
        metric1, _ = metrics
        with pytest.raises(ValidationError):
            MetricSpatialDimension.objects.create(
                metric=metric1,
                h3_index="000000000000000",  # Invalid H3 index
            )

    def test_metric_spatial_dimension_non_hexadecimal_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with not an hexadecimal h3 index.
        """
        _, metric2 = metrics
        with pytest.raises(ValidationError):
            MetricSpatialDimension.objects.create(
                metric=metric2,
                h3_index=603502369715519487,  # Non hexadecimal valid h3 index
            )

    def test_metric_spatial_dimension_invalid_resolution_h3_index_validation(self, metrics):
        """
        Test the behavior of validation error when trying to create metric with invalid resolution h3 index.
        """
        metric1, _ = metrics
        with pytest.raises(ValidationError):
            MetricSpatialDimension.objects.create(
                metric=metric1,
                h3_index=utils.h3_index_lvl8,  # Valid h3 index but invalid resolution
            )
