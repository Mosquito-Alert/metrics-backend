import pytest
from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection, reset_queries

from anomaly_detection.regions.models import AutonomousCommunity, Country


@pytest.fixture
def multipolygon():
    """Fixture to create a MultiPolygon instance."""
    # Create a MultiPolygon instance with one polygon
    polygon = Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))
    multipolygon = MultiPolygon(polygon)
    return multipolygon


@pytest.fixture
def autonomous_community(multipolygon):
    """
    Fixture to create an AutonomousCommunity instance.
    """
    settings.DEBUG = True  # Enable DEBUG mode for testing
    country = Country.objects.create(
        code='ESP',
        name='Spain',
        alt_name='Espana',
        continent='Europe',
    )
    return AutonomousCommunity.objects.create(
        code='ESP.1_1',
        name='Test Autonomous Community',
        alt_name='Test Alt Name',
        country=country,
        geometry=multipolygon
    )


@pytest.mark.django_db
class TestRegionManager:
    """
    Test the RegionManager class.
    """

    def test_geometry_is_deferred_by_default(self, autonomous_community):
        """
        Test that the geometry field is deferred by default.
        """
        # Reset queries to count the number of queries executed
        reset_queries()

        # Get the first autonomous community
        region = AutonomousCommunity.objects.first()

        # Accessing name should NOT trigger additional query
        _ = region.name
        queries_after_name = len(connection.queries)

        # Accessing geometry SHOULD trigger additional query (deferred)
        _ = region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_name == 1
        assert queries_after_geometry > 1

    def test_with_geometry_includes_geometry(self, autonomous_community):
        """
        Test that the with_geometry method includes the geometry field.
        """
        # Reset queries to count the number of queries executed
        reset_queries()

        # Get the first autonomous community with geometry
        region = AutonomousCommunity.objects.with_geometry().first()

        # Accessing geometry should NOT cause extra query
        _ = region.geometry
        queries_after_geometry = len(connection.queries)

        assert queries_after_geometry == 1
