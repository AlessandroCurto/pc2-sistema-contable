"""Etiqueta {% icono "nombre" %}: dibuja uno de los SVG del sprite iconos.html."""

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(name="icono")
def icono(nombre: str, tamano: int = 18, clase: str = "icono"):
    return format_html(
        '<svg class="{}" width="{}" height="{}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true" focusable="false">'
        '<use href="#icono-{}" /></svg>',
        clase,
        tamano,
        tamano,
        nombre,
    )
