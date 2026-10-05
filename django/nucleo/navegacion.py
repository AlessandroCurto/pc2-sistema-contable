"""Menú de la aplicación. Un solo lugar define las secciones y su orden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EntradaMenu:
    ruta: str
    etiqueta: str
    descripcion: str
    #: Nombre del icono SVG que dibuja la plantilla iconos.html.
    icono: str
    grupo: str
    #: True cuando la pantalla necesita un caso abierto.
    requiere_caso: bool


MENU: List[EntradaMenu] = [
    EntradaMenu("inicio", "Inicio", "Resumen del caso abierto y accesos rápidos", "inicio", "Principal", False),
    EntradaMenu("casos", "Casos", "Crear, abrir, importar y exportar casos contables", "casos", "Principal", False),
    EntradaMenu(
        "plan_cuentas",
        "Plan de Cuentas",
        "Gestionar el catálogo de cuentas contables y su clasificación",
        "plan",
        "Operaciones",
        True,
    ),
    EntradaMenu(
        "registrar_asiento",
        "Registrar Asiento",
        "Crear un nuevo asiento contable con sus movimientos al Debe y al Haber",
        "asiento",
        "Operaciones",
        True,
    ),
    EntradaMenu(
        "libro_diario",
        "Libro Diario",
        "Consultar todos los asientos registrados ordenados por fecha",
        "diario",
        "Reportes",
        True,
    ),
    EntradaMenu(
        "libro_mayor",
        "Libro Mayor",
        "Ver los movimientos y saldos agrupados por cada cuenta contable",
        "mayor",
        "Reportes",
        True,
    ),
    EntradaMenu(
        "balance_comprobacion",
        "Balance de Comprobación",
        "Verificar que los totales del Debe y del Haber estén cuadrados",
        "balanza",
        "Reportes",
        True,
    ),
    EntradaMenu(
        "estado_resultados",
        "Estado de Resultados",
        "Calcular la utilidad o pérdida del período",
        "resultados",
        "Reportes",
        True,
    ),
    EntradaMenu(
        "balance_general",
        "Balance General",
        "Verificar la ecuación contable: Activo = Pasivo + Patrimonio",
        "balance_general",
        "Reportes",
        True,
    ),
    EntradaMenu(
        "reporte",
        "Generar PDF / Enviar",
        "Reunir todos los reportes en un solo archivo PDF",
        "pdf",
        "Descargas",
        True,
    ),
    EntradaMenu(
        "configuracion",
        "Configuración",
        "Datos de la empresa, período e impuesto a la renta",
        "ajustes",
        "Sistema",
        True,
    ),
]

GRUPOS_MENU = ["Principal", "Operaciones", "Reportes", "Descargas", "Sistema"]

ACCESOS_RAPIDOS = [
    "plan_cuentas",
    "registrar_asiento",
    "balance_comprobacion",
    "estado_resultados",
    "libro_diario",
    "libro_mayor",
    "balance_general",
    "reporte",
]


def entrada_de_ruta(nombre_ruta: str):
    for entrada in MENU:
        if entrada.ruta == nombre_ruta:
            return entrada
    return None


def accesos_rapidos():
    return [entrada for entrada in MENU if entrada.ruta in ACCESOS_RAPIDOS]
