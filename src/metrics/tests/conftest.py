from django.conf import settings
from django.db import reset_queries, connection as db_connection
import pytest

from src.metrics.models import Metric, MetricSpatialDimension, MetricTimeDimension, MetricValue, PredictorConfig
from . import utils


@pytest.fixture
def connection():
    """Fixture to reset queries after each test and return the connection."""
    settings.DEBUG = True
    # Reset queries to count the number of queries executed
    reset_queries()
    return db_connection


# TODO: Use factory_boy
@pytest.fixture
def metrics():
    """Fixture to create a Metric instance."""
    metric1 = Metric.objects.create(
        name="Metric 1",
        code="metric_1",
        time_dimension_step=Metric.TimeDimensionStepType.DAILY,
        is_predictable=True,
        h3_resolution=6
    )
    metric2 = Metric.objects.create(
        name="Metric 2",
        code="metric_2",
        time_dimension_step=Metric.TimeDimensionStepType.HOURLY,
        is_predictable=False,
        h3_resolution=8
    )
    return metric1, metric2


@pytest.fixture
def predictor_configs(metrics):
    """Fixture to create a PredictorConfig instance."""
    metric1, metric2 = metrics
    predictor_config1 = PredictorConfig.objects.create(
        metric=metric1,
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        growth='linear'
    )
    predictor_config2 = PredictorConfig.objects.create(
        metric=metric2,
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=True,
        growth='logistic'
    )
    return predictor_config1, predictor_config2


@pytest.fixture
def metric_time_dimensions(metrics):
    """Fixture to create a MetricTimeDimension instance."""
    metric1, metric2 = metrics
    metric_time_dimension1 = MetricTimeDimension.objects.create(
        metric=metric1,
        time=utils.time1,
        type=MetricTimeDimension.MetricValueType.REANALYSIS
    )
    metric_time_dimension2 = MetricTimeDimension.objects.create(
        metric=metric1,
        time=utils.time2,
        type=MetricTimeDimension.MetricValueType.FORECAST
    )
    metric_time_dimension3 = MetricTimeDimension.objects.create(
        metric=metric2,
        time=utils.time1,
        type=MetricTimeDimension.MetricValueType.REANALYSIS
    )
    return metric_time_dimension1, metric_time_dimension2, metric_time_dimension3


@pytest.fixture
def metric_spatial_dimensions(metrics):
    """Fixture to create a MetricSpatialDimension instance."""
    metric1, metric2 = metrics
    metric_spatial_dimension1 = MetricSpatialDimension.objects.create(
        metric=metric1,
        h3_index=utils.h3_index1,
    )
    metric_spatial_dimension2 = MetricSpatialDimension.objects.create(
        metric=metric1,
        h3_index=utils.h3_index2,
    )
    metric_spatial_dimension3 = MetricSpatialDimension.objects.create(
        metric=metric2,
        h3_index=utils.h3_index_lvl8,
    )
    return metric_spatial_dimension1, metric_spatial_dimension2, metric_spatial_dimension3


@pytest.fixture
def metric_values(metric_time_dimensions, metric_spatial_dimensions):
    """Fixture to create MetricValue instances."""
    time_dimension1, time_dimension2, time_dimension3 = metric_time_dimensions
    spatial_dimension1, spatial_dimension2, spatial_dimension3 = metric_spatial_dimensions
    metric_value1 = MetricValue.objects.create(
        time_dimension=time_dimension1,
        spatial_dimension=spatial_dimension1,
        value=0.123,
    )
    metric_value2 = MetricValue.objects.create(
        time_dimension=time_dimension1,
        spatial_dimension=spatial_dimension2,
        value=0.456,
    )
    metric_value3 = MetricValue.objects.create(
        time_dimension=time_dimension2,
        spatial_dimension=spatial_dimension1,
        value=0.789,
        predicted_value=0.654,
        lower_confidence_band=0.500,
        upper_confidence_band=0.800
    )
    metric_value3 = MetricValue.objects.create(
        time_dimension=time_dimension2,
        spatial_dimension=spatial_dimension2,
        value=0.789,
    )
    metric_value4 = MetricValue.objects.create(
        time_dimension=time_dimension3,
        spatial_dimension=spatial_dimension3,
        value=0.489,
    )
    return metric_value1, metric_value2, metric_value3, metric_value4
