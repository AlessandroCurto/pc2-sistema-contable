"""Cuál es el caso abierto. Se guarda en la sesión, no en un usuario.

La versión web estática guardaba el caso activo en el navegador; aquí se guarda
en la sesión de Django, así cada persona que abre el servidor trabaja con el
caso que eligió sin necesidad de login.
"""

from __future__ import annotations

from typing import Optional

CLAVE_CASO = "caso_activo_id"


def caso_activo(request) -> Optional[object]:
    """Devuelve el caso abierto, o el más reciente si la sesión no tiene uno."""
    from .models import Caso

    id_caso = request.session.get(CLAVE_CASO)
    if id_caso:
        caso = Caso.objects.filter(pk=id_caso).first()
        if caso is not None:
            return caso
        request.session.pop(CLAVE_CASO, None)
    caso = Caso.objects.order_by("-actualizado_en").first()
    if caso is not None:
        request.session[CLAVE_CASO] = caso.pk
    return caso


def abrir_caso(request, caso) -> None:
    request.session[CLAVE_CASO] = caso.pk


def cerrar_caso(request) -> None:
    request.session.pop(CLAVE_CASO, None)
