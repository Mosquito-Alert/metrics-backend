from django.conf import settings
from django.db import reset_queries, connection as db_connection
import pytest

from src.metrics.models import Metric, MetricRegionalStatistics, MetricStatistics, MetricValue, PredictorConfig
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
def metric_values(metrics):
    """Fixture to create MetricValue instances."""
    metric1, metric2 = metrics
    metric_value1 = MetricValue.objects.create(
        metric=metric1,
        h3_index=utils.h3_index1,
        time=utils.time1,
        value=0.123,
        type=MetricValue.MetricValueType.REANALYSIS
    )
    metric_value2 = MetricValue.objects.create(
        metric=metric1,
        h3_index=utils.h3_index2,
        time=utils.time1,
        value=0.456,
        type=MetricValue.MetricValueType.REANALYSIS,
        predicted_value=0.654,
        lower_confidence_band=0.500,
        upper_confidence_band=0.800
    )
    metric_value3 = MetricValue.objects.create(
        metric=metric1,
        h3_index=utils.h3_index3,
        time=utils.time1,
        value=0.789,
        type=MetricValue.MetricValueType.FORECAST
    )
    metric_value4 = MetricValue.objects.create(
        metric=metric1,
        h3_index=utils.h3_index1,
        time=utils.time2,
        value=0.489,
        type=MetricValue.MetricValueType.REANALYSIS
    )
    metric_value5 = MetricValue.objects.create(
        metric=metric2,
        h3_index=utils.h3_index_lvl8,
        time=utils.time1,
        value=0.125,
        type=MetricValue.MetricValueType.REANALYSIS
    )
    return metric_value1, metric_value2, metric_value3, metric_value4, metric_value5


@pytest.fixture
def metric_statistics(metrics):
    """Fixture to create a MetricStatistics instance."""
    metric1, metric2 = metrics
    metric_statistics1 = MetricStatistics.objects.create(
        metric=metric1,
        time=utils.time1,
    )
    metric_statistics2 = MetricStatistics.objects.create(
        metric=metric2,
        time=utils.time2,
    )
    return metric_statistics1, metric_statistics2


@pytest.fixture
def metric_regional_statistics(metrics):
    """Fixture to create a MetricRegionalStatistics instance."""
    metric1, metric2 = metrics
    metric_regional_statistics1 = MetricRegionalStatistics.objects.create(
        metric=metric1,
        region=utils.region1,
        time=utils.time1,
    )
    metric_regional_statistics2 = MetricRegionalStatistics.objects.create(
        metric=metric2,
        region=utils.region2,
        time=utils.time2,
    )
    return metric_regional_statistics1, metric_regional_statistics2
