from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

from .managers import RegionManager


class AbstractRegion(models.Model):
    """
    Abstract model to store the region data.
    """
    code = models.CharField(
        max_length=32,
        unique=True,
        null=False,
        blank=False,
        verbose_name=_('Code'),
        help_text=_('The unique code that identifies the region.')
    )
    name = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        verbose_name=_('Name'),
        help_text=_('The name of the region.')
    )
    alt_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Alternative names.'),
        help_text=_('Alternative names for the region. If there is more than one, they will be delimited by "|".')
    )
    geometry = models.MultiPolygonField(
        blank=False,
        null=False,
        verbose_name=_('Geometry.'),
        help_text=_('Geometry of the region.')
    )

    # Manager
    objects = RegionManager()

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        ordering = ['code']
        indexes = [
            models.Index(fields=['name'])
        ]


class Country(models.Model):
    """
    Model to store the country data.
    """
    code = models.CharField(
        max_length=32,
        unique=True,
        null=False,
        blank=False,
        verbose_name=_('Code'),
        help_text=_('The unique code that identifies the region.')
    )
    name = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        verbose_name=_('Name'),
        help_text=_('The name of the region.')
    )
    alt_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Alternative names.'),
        help_text=_('Alternative names for the region. If there is more than one, they will be delimited by "|".')
    )
    continent = models.CharField(
        max_length=64,
        null=False,
        blank=False,
        verbose_name=_('Continent'),
        help_text=_('The name of the continent.')
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'


class AutonomousCommunity(AbstractRegion):
    """
    Model to store the autonomous community data.
    """
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='autonomous_communities')

    class Meta(AbstractRegion.Meta):
        verbose_name = 'Autonomous Community'
        verbose_name_plural = 'Autonomous Communities'


class Province(AbstractRegion):
    """
    Model to store the province data.
    """
    autonomous_community = models.ForeignKey(AutonomousCommunity, on_delete=models.CASCADE, related_name='provinces')

    class Meta(AbstractRegion.Meta):
        verbose_name = 'Province'
        verbose_name_plural = 'Provinces'


class Municipality(AbstractRegion):
    """
    Model to store the municipality data.
    """
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='municipalities')

    class Meta(AbstractRegion.Meta):
        verbose_name = 'Municipality'
        verbose_name_plural = 'Municipalities'
