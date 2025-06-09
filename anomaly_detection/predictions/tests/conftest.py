from django.conf import settings
from django.db import reset_queries, connection as db_connection
import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from anomaly_detection.regions.models import (AutonomousCommunity, Country,
                                              Municipality, Province)
from anomaly_detection.predictions.models import Metric, MetricExecution, MetricSeasonality


@pytest.fixture
def connection():
    """Fixture to reset queries after each test and return the connection."""
    settings.DEBUG = True
    # Reset queries to count the number of queries executed
    reset_queries()
    return db_connection


@pytest.fixture
def multipolygon():
    """Fixture to create a MultiPolygon instance."""
    # Create a MultiPolygon instance with one polygon
    polygon = Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))
    multipolygon = MultiPolygon(polygon)
    return multipolygon


@pytest.fixture
def municipality(multipolygon):
    """Fixture to create a Municipality instance."""
    country = Country.objects.create(
        code='ESP',
        name='Spain',
        alt_name='Espana',
        continent='Europe',
    )
    autonomous_community = AutonomousCommunity.objects.create(
        code='ESP.1_1',
        name='Test Autonomous Community',
        alt_name='Test Alt Name',
        country=country,
        geometry=multipolygon
    )
    province = Province.objects.create(
        code='ESP.1.1_1',
        name='Test Province',
        alt_name='Test Alt Name',
        autonomous_community=autonomous_community,
        geometry=multipolygon
    )
    municipality1 = Municipality.objects.create(
        code='ESP.1.1.1.1_1',
        name='Test Municipality',
        alt_name='Test Alt Name',
        province=province,
        geometry=multipolygon
    )
    municipality2 = Municipality.objects.create(
        code='ESP.1.1.1.2_1',
        name='Test Municipality 2',
        alt_name='Test Alt Name 2',
        province=province,
        geometry=multipolygon
    )
    return municipality1, municipality2


# TODO: Use factory_boy
@pytest.fixture
def metrics(municipality):
    """Fixture to create a Metric instance."""
    municipality1, municipality2 = municipality
    metric1 = Metric.objects.create(
        region=municipality1,
        date='2023-01-01',
        value=0.8,
        predicted_value=0.85,
        lower_value=0.5,
        upper_value=1.0,
        trend=0.1,
    )
    metric2 = Metric.objects.create(
        region=municipality1,
        date='2023-01-02',
        value=0.9,
        predicted_value=0.75,
        lower_value=0.6,
        upper_value=0.8,
        trend=0.2,
    )
    metric3 = Metric.objects.create(
        region=municipality1,
        date='2023-01-03',
        value=0.4,
        predicted_value=0.75,
        lower_value=0.5,
        upper_value=0.9,
        trend=0.3,
    )
    metric4 = Metric.objects.create(
        region=municipality2,
        date='2023-01-03',
        value=0.7,
        predicted_value=0.85,
        lower_value=0.4,
        upper_value=0.9,
        trend=0.1,
    )
    return metric1, metric2, metric3, metric4


@pytest.fixture
def seasonalities(municipality):
    """Fixture to create a MetricSeasonality instance."""
    municipality1, municipality2 = municipality
    seasonality1 = MetricSeasonality.objects.create(
        region=municipality1,
        index=0,
        yearly_value=0.5
    )
    seasonality2 = MetricSeasonality.objects.create(
        region=municipality1,
        index=1,
        yearly_value=0.6
    )
    seasonality3 = MetricSeasonality.objects.create(
        region=municipality2,
        index=0,
        yearly_value=0.65
    )
    return seasonality1, seasonality2, seasonality3


@pytest.fixture
def metric_executions():
    """Fixture to create a MetricExecution instance."""
    metric_execution1 = MetricExecution.objects.create(
        date='2024-01-31',
        success_percentage=0.99
    )
    metric_execution2 = MetricExecution.objects.create(
        date='2024-01-30',
        success_percentage=1
    )
    metric_execution3 = MetricExecution.objects.create(
        date='2025-01-30',
        success_percentage=0.93
    )
    return metric_execution1, metric_execution2, metric_execution3
