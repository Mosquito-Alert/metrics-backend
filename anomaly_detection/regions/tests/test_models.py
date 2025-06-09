from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import IntegrityError
import pytest

from anomaly_detection.regions.models import AutonomousCommunity, Country, Municipality, Province


@pytest.fixture
def multipolygon():
    """Fixture to create a MultiPolygon instance."""
    # Create a MultiPolygon instance with one polygon
    polygon = Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))
    multipolygon = MultiPolygon(polygon)
    return multipolygon


@pytest.fixture
def country():
    """Fixture to create a Country instance."""
    return Country.objects.create(
        code='ESP',
        name='Spain',
        alt_name='Espana',
        continent='Europe',
    )


@pytest.fixture
def autonomous_community(country, multipolygon):
    """Fixture to create an AutonomousCommunity instance."""
    return AutonomousCommunity.objects.create(
        code='ESP.1_1',
        name='Test Autonomous Community',
        alt_name='Test Alt Name',
        country=country,
        geometry=multipolygon
    )


@pytest.fixture
def province(autonomous_community, multipolygon):
    """Fixture to create a Province instance."""
    return Province.objects.create(
        code='ESP.1.1_1',
        name='Test Province',
        alt_name='Test Alt Name',
        autonomous_community=autonomous_community,
        geometry=multipolygon
    )


@pytest.fixture
def municipality(province, multipolygon):
    """Fixture to create a Municipality instance."""
    return Municipality.objects.create(
        code='ESP.1.1.1.1_1',
        name='Test Municipality',
        alt_name='Test Alt Name',
        province=province,
        geometry=multipolygon
    )


@pytest.mark.django_db
class TestMunicipalityModel:
    """Test case for the Municipality model."""

    def test_municipality_creation(self, province, municipality, multipolygon):
        """Test the creation of a Municipality instance."""
        assert isinstance(municipality, Municipality)
        assert municipality.code == 'ESP.1.1.1.1_1'
        assert municipality.name == 'Test Municipality'
        assert municipality.alt_name == 'Test Alt Name'
        assert municipality.geometry == multipolygon
        assert municipality.province == province

    def test_municipality_str(self, municipality):
        """Test the string representation of a Municipality instance."""
        assert str(municipality) == 'Test Municipality'

    def test_municipality_meta(self):
        """Test the meta options of the Municipality model."""
        assert Municipality._meta.verbose_name == 'Municipality'
        assert Municipality._meta.verbose_name_plural == 'Municipalities'
        assert Municipality._meta.ordering == ['code']
        assert 'name' in [field for field in Municipality._meta.indexes[0].fields]

    def test_municipality_geometry(self, multipolygon, municipality):
        """Test the one-to-one relationship between Municipality and Geometry."""
        geometry = municipality.geometry
        assert geometry == multipolygon
        assert geometry.srid == 4326

    def test_municipality_geometry_cannot_be_null(self, province):
        """Test that the geometry field cannot be null."""
        with pytest.raises(IntegrityError):
            Municipality.objects.create(
                code='ESP.1.1.1.2_1',
                name='Test Municipality 2',
                alt_name='Test Alt Name 2',
                province=province
            )

    def test_municipality_province_relation(self, province, municipality):
        """Test the foreign key relationship between Municipality and Province."""
        assert municipality.province == province
        assert municipality in province.municipalities.all()

    def test_municipality_province_cannot_be_null(self, multipolygon):
        """Test that the province field cannot be null."""
        with pytest.raises(IntegrityError):
            Municipality.objects.create(
                code='ESP.1.1.1.3_1',
                name='Test Municipality 3',
                alt_name='Test Alt Name 3',
                geometry=multipolygon
            )


@pytest.mark.django_db
class TestProvinceModel:
    """Test case for the Province model."""

    def test_province_creation(self, autonomous_community, province, multipolygon):
        """Test the creation of a Province instance."""
        assert isinstance(province, Province)
        assert province.code == 'ESP.1.1_1'
        assert province.name == 'Test Province'
        assert province.alt_name == 'Test Alt Name'
        assert province.geometry == multipolygon
        assert province.autonomous_community == autonomous_community

    def test_province_str(self, province):
        """Test the string representation of a Province instance."""
        assert str(province) == 'Test Province'

    def test_province_meta(self):
        """Test the meta options of the Province model."""
        assert Province._meta.verbose_name == 'Province'
        assert Province._meta.verbose_name_plural == 'Provinces'
        assert Province._meta.ordering == ['code']
        assert 'name' in [field for field in Province._meta.indexes[0].fields]

    def test_province_geometry(self, multipolygon, province):
        """Test the one-to-one relationship between Province and Geometry."""
        geometry = province.geometry
        assert geometry == multipolygon
        assert geometry.srid == 4326

    def test_province_geometry_cannot_be_null(self, autonomous_community):
        """Test that the geometry field cannot be null."""
        with pytest.raises(IntegrityError):
            Province.objects.create(
                code='ESP.1.1_2',
                name='Test Province 2',
                alt_name='Test Alt Name 2',
                autonomous_community=autonomous_community
            )

    def test_province_autonomous_community_relation(self, autonomous_community, province):
        """Test the foreign key relationship between Province and AutonomousCommunity."""
        assert province.autonomous_community == autonomous_community
        assert province in autonomous_community.provinces.all()

    def test_province_autonomous_community_cannot_be_null(self):
        """Test that the autonomous community field cannot be null."""
        with pytest.raises(IntegrityError):
            Province.objects.create(
                code='ESP.1.1_2',
                name='Test Province 2',
                alt_name='Test Alt Name 2'
            )


@pytest.mark.django_db
class TestAutonomousCommunityModel:
    """Test case for the AutonomousCommunity model."""

    def test_autonomous_community_creation(self, country, autonomous_community):
        """Test the creation of an AutonomousCommunity instance."""
        assert isinstance(autonomous_community, AutonomousCommunity)
        assert autonomous_community.code == 'ESP.1_1'
        assert autonomous_community.name == 'Test Autonomous Community'
        assert autonomous_community.alt_name == 'Test Alt Name'
        assert autonomous_community.country == country

    def test_autonomous_community_str(self, autonomous_community):
        """Test the string representation of an AutonomousCommunity instance."""
        assert str(autonomous_community) == 'Test Autonomous Community'

    def test_autonomous_community_meta(self):
        """Test the meta options of the AutonomousCommunity model."""
        assert AutonomousCommunity._meta.verbose_name == 'Autonomous Community'
        assert AutonomousCommunity._meta.verbose_name_plural == 'Autonomous Communities'
        assert Province._meta.ordering == ['code']
        assert 'name' in [field for field in Province._meta.indexes[0].fields]

    def test_autonomous_community_geometry(self, multipolygon, autonomous_community):
        """Test the one-to-one relationship between AutonomousCommunity and Geometry."""
        geometry = autonomous_community.geometry
        assert geometry == multipolygon
        assert geometry.srid == 4326

    def test_autonomous_community_geometry_cannot_be_null(self, country):
        """Test that the geometry field cannot be null."""
        with pytest.raises(IntegrityError):
            AutonomousCommunity.objects.create(
                code='ESP.1_2',
                name='Test Autonomous Community 2',
                alt_name='Test Alt Name 2',
                country=country
            )

    def test_autonomous_community_country_relation(self, country, autonomous_community):
        """Test the foreign key relationship between AutonomousCommunity and Country."""
        assert autonomous_community.country == country
        assert autonomous_community in country.autonomous_communities.all()

    def test_autonomous_community_country_cannot_be_null(self, multipolygon):
        """Test that the country field cannot be null."""
        with pytest.raises(IntegrityError):
            AutonomousCommunity.objects.create(
                code='ESP.1_2',
                name='Test Autonomous Community 2',
                alt_name='Test Alt Name 2',
                geometry=multipolygon
            )


@pytest.mark.django_db
class TestCountryModel:
    """Test case for the Country model."""

    def test_country_creation(self, country):
        """Test the creation of a Country instance."""
        assert isinstance(country, Country)
        assert country.code == 'ESP'
        assert country.name == 'Spain'
        assert country.alt_name == 'Espana'
        assert country.continent == 'Europe'

    def test_country_str(self, country):
        """Test the string representation of a Country instance."""
        assert str(country) == 'Spain'

    def test_country_meta(self):
        """Test the meta options of the Country model."""
        assert Country._meta.verbose_name == 'Country'
        assert Country._meta.verbose_name_plural == 'Countries'
