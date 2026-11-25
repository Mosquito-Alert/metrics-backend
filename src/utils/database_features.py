"""
Define PostgreSQL features (types, constraints) that aren't natively supported in Django for use in Django models.
"""
from django.db import models


class RealField(models.FloatField):
    # 32-bit floating point number, similar to PostgreSQL's "real" type. Single point precision.
    def db_type(self, connection):
        # TODO: Would be useful to check that postgres (independently of the extensions) is the connection backend
        # If not, either raise an error or return a FloatField
        return "real"
