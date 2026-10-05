"""Contexto que toda plantilla recibe: el menú y el caso abierto."""

from __future__ import annotations

from .navegacion import GRUPOS_MENU, MENU, entrada_de_ruta
from .sesion import caso_activo


def navegacion(request):
    nombre_ruta = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    actual = entrada_de_ruta(nombre_ruta)
    caso = caso_activo(request)
    grupos = []
    for grupo in GRUPOS_MENU:
        entradas = [entrada for entrada in MENU if entrada.grupo == grupo]
        if entradas:
            grupos.append({"nombre": grupo, "entradas": entradas})
    return {
        "menu_grupos": grupos,
        "ruta_actual": nombre_ruta,
        "entrada_actual": actual,
        "caso_activo": caso,
    }
