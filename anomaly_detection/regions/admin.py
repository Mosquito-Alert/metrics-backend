
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from anomaly_detection.regions.models import AutonomousCommunity, Country, Municipality, Province


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name', 'alt_name')
    ordering = ['id']
    fieldsets = (
        (_('Fields'), {
            'fields': ['code', 'name', 'alt_name']
        }),
        (_('Geometry'), {
            'fields': ['geometry']
        }),
    )
    # readonly_fields = ['geometry']


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name', 'alt_name')
    ordering = ['id']
    fieldsets = (
        (_('Fields'), {
            'fields': ['code', 'name', 'alt_name']
        }),
        (_('Geometry'), {
            'fields': ['geometry']
        }),
    )
    # readonly_fields = ['geometry']


@admin.register(AutonomousCommunity)
class AutonomousCommunityAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name', 'alt_name')
    ordering = ['id']
    fieldsets = (
        (_('Fields'), {
            'fields': ['code', 'name', 'alt_name']
        }),
        (_('Geometry'), {
            'fields': ['geometry']
        }),
    )
    # readonly_fields = ['geometry']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name', 'alt_name')
    ordering = ['id']
    fieldsets = (
        (_('Fields'), {
            'fields': ['code', 'name', 'alt_name']
        }),
    )
