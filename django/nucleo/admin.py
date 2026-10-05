"""Registro en el admin de Django. Sirve para revisar los datos en crudo."""

from django.contrib import admin

from .models import Asiento, Caso, Cuenta, LineaAsiento


class LineaEnLinea(admin.TabularInline):
    model = LineaAsiento
    extra = 0


@admin.register(Caso)
class CasoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "razon_social", "ruc", "tasa_impuesto_renta", "actualizado_en")
    search_fields = ("nombre", "razon_social", "ruc")


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "rubro", "caso")
    list_filter = ("tipo", "caso")
    search_fields = ("codigo", "nombre")


@admin.register(Asiento)
class AsientoAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "glosa", "caso")
    list_filter = ("caso",)
    inlines = [LineaEnLinea]
