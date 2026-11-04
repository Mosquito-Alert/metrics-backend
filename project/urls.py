"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (SpectacularAPIView, SpectacularJSONAPIView,
                                   SpectacularRedocView,
                                   SpectacularSwaggerView)

api_version = 'v2'

urlpatterns = [
    path('admin/', admin.site.urls),
    path(f'{api_version}/schema/openapi.yml', SpectacularAPIView.as_view(api_version=api_version), name='api-schema'),
    path(f'{api_version}/schema/openapi.json', SpectacularJSONAPIView.as_view(api_version=api_version),
         name='api-schema-json'),
    path(f'{api_version}/', SpectacularRedocView.as_view(url_name='api-schema'), name='redoc'),
    path(f'{api_version}/', include('src.metrics.urls', namespace='metrics')),
    path(f'{api_version}/', include('src.tasks.urls', namespace='tasks')),
]


if settings.DEBUG:
    urlpatterns += [
        path('silk/', include('silk.urls', namespace='silk')),
        path(
            f'{api_version}/swagger/',
            SpectacularSwaggerView.as_view(url_name="api-schema"),
            name="swagger-ui",
        ),
    ]
