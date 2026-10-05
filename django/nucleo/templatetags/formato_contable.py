"""Filtros de plantilla: los mismos formatos del dominio, usables en el HTML."""

from django import template

from ..dominio.formato import formatear_fecha, formatear_moneda, formatear_numero
from ..dominio.numeros import es_cero as _es_cero

register = template.Library()


@register.filter(name="numero")
def numero(valor):
    """1234.5 -> 1,234.50"""
    return formatear_numero(valor)


@register.filter(name="moneda")
def moneda(valor, simbolo="S/"):
    """1234.5 -> S/ 1,234.50"""
    return formatear_moneda(valor, simbolo)


@register.filter(name="fecha_pe")
def fecha_pe(valor):
    """date(2024, 1, 31) -> 31/01/2024"""
    return formatear_fecha(valor)


@register.filter(name="numero_o_vacio")
def numero_o_vacio(valor):
    """Las columnas Debe y Haber dejan la celda vacia cuando el importe es cero."""
    return "" if _es_cero(valor) else formatear_numero(valor)


@register.filter(name="es_cero")
def es_cero(valor):
    return _es_cero(valor)
