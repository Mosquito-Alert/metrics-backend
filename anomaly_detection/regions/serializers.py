

import json
from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from anomaly_detection.regions.models import Municipality


class MunicipalitySerializer(ModelSerializer):
    """
    Serializer for the Municipality model.
    """
    province = SerializerMethodField()

    def get_province(self, obj=None) -> str:
        """
        Get the province name from the province related model.
        """
        if obj and obj.province:
            return obj.province.name
        return None

    class Meta:
        model = Municipality
        fields = ['id', 'code', 'name', 'alt_name', 'province']


class MunicipalityRetrieveSerializer(GeoFeatureModelSerializer):
    """
    Serializer for the Municipality model.
    """
    province = SerializerMethodField()
    geometry = SerializerMethodField()

    def get_province(self, obj=None) -> str:
        """
        Get the province name from the province related model.
        """
        if obj and obj.province:
            return obj.province.name
        return None

    def get_geometry(self, obj):
        return json.loads(obj.geometry.geojson)

    class Meta:
        model = Municipality
        geo_field = 'geometry'
        fields = ['id', 'code', 'name', 'alt_name', 'province', 'geometry']
        extra_kwargs = {
            'geometry': {'allow_null': True},
        }
