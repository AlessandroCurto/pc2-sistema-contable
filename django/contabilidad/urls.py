"""Direcciones del proyecto. Toda la aplicación vive en la app `nucleo`."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("nucleo.urls")),
]
