"""Plantillas de plan de cuentas. Son solo datos: ningún reporte depende de ellas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class DefinicionCuenta:
    codigo: str
    nombre: str
    tipo: str
    rubro: Optional[str] = None


@dataclass(frozen=True)
class PlantillaCuentas:
    id: str
    nombre: str
    descripcion: str
    cuentas: List[DefinicionCuenta]


PCGE = [
    DefinicionCuenta("10", "Efectivo y equivalentes de efectivo", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("12", "Cuentas por cobrar comerciales", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("14", "Cuentas por cobrar al personal y accionistas", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("20", "Mercaderías", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("25", "Materiales auxiliares, suministros y repuestos", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("33", "Inmuebles, maquinaria y equipo", "ACTIVO", "NO_CORRIENTE"),
    DefinicionCuenta("34", "Intangibles", "ACTIVO", "NO_CORRIENTE"),
    DefinicionCuenta("40", "Tributos por pagar", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("41", "Remuneraciones por pagar", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("42", "Cuentas por pagar comerciales", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("45", "Obligaciones financieras", "PASIVO", "NO_CORRIENTE"),
    DefinicionCuenta("50", "Capital", "PATRIMONIO"),
    DefinicionCuenta("59", "Resultados acumulados", "PATRIMONIO"),
    DefinicionCuenta("60", "Compras", "GASTO", "COSTO_VENTAS"),
    DefinicionCuenta("62", "Gastos de personal", "GASTO", "GASTO_ADMINISTRACION"),
    DefinicionCuenta("63", "Gastos de servicios prestados por terceros", "GASTO", "GASTO_ADMINISTRACION"),
    DefinicionCuenta("65", "Otros gastos de gestión", "GASTO", "OTRO_GASTO"),
    DefinicionCuenta("67", "Gastos financieros", "GASTO", "GASTO_FINANCIERO"),
    DefinicionCuenta("69", "Costo de ventas", "GASTO", "COSTO_VENTAS"),
    DefinicionCuenta("70", "Ventas", "INGRESO", "VENTAS"),
    DefinicionCuenta("74", "Descuentos, rebajas y bonificaciones concedidos", "INGRESO", "DESCUENTOS_VENTAS"),
    DefinicionCuenta("75", "Otros ingresos de gestión", "INGRESO", "OTRO_INGRESO"),
    DefinicionCuenta("77", "Ingresos financieros", "INGRESO", "INGRESO_FINANCIERO"),
    DefinicionCuenta("94", "Gastos de administración", "GASTO", "GASTO_ADMINISTRACION"),
    DefinicionCuenta("95", "Gastos de ventas", "GASTO", "GASTO_VENTAS"),
]

NUMERADO = [
    DefinicionCuenta("101", "Caja", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("102", "Banco", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("103", "Clientes", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("104", "Letras por Cobrar", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("105", "Mercaderías", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("106", "IGV Crédito Fiscal", "ACTIVO", "CORRIENTE"),
    DefinicionCuenta("107", "Muebles y Enseres", "ACTIVO", "NO_CORRIENTE"),
    DefinicionCuenta("201", "Proveedores", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("202", "Letras por Pagar", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("203", "IGV Débito Fiscal", "PASIVO", "CORRIENTE"),
    DefinicionCuenta("204", "Préstamos Bancarios", "PASIVO", "NO_CORRIENTE"),
    DefinicionCuenta("301", "Capital", "PATRIMONIO"),
    DefinicionCuenta("302", "Resultados Acumulados", "PATRIMONIO"),
    DefinicionCuenta("401", "Ventas", "INGRESO", "VENTAS"),
    DefinicionCuenta("402", "Devoluciones sobre Ventas", "INGRESO", "DEVOLUCIONES_VENTAS"),
    DefinicionCuenta("403", "Ingresos Financieros", "INGRESO", "INGRESO_FINANCIERO"),
    DefinicionCuenta("501", "Gastos de Arriendo", "GASTO", "GASTO_ADMINISTRACION"),
    DefinicionCuenta("502", "Costo de Ventas", "GASTO", "COSTO_VENTAS"),
    DefinicionCuenta("503", "Gastos de Ventas", "GASTO", "GASTO_VENTAS"),
    DefinicionCuenta("504", "Gastos Financieros", "GASTO", "GASTO_FINANCIERO"),
    DefinicionCuenta("505", "Gastos de Personal", "GASTO", "GASTO_ADMINISTRACION"),
]

PLANTILLAS_CUENTAS = [
    PlantillaCuentas(
        id="pcge",
        nombre="PCGE simplificado (Perú)",
        descripcion="Cuentas de dos dígitos: 10 Efectivo, 20 Mercaderías, 50 Capital, 70 Ventas...",
        cuentas=PCGE,
    ),
    PlantillaCuentas(
        id="numerado",
        nombre="Numeración por grupos (101, 201, 301...)",
        descripcion="Caja, Banco, Clientes, Proveedores, Capital, Ventas, Costo de ventas...",
        cuentas=NUMERADO,
    ),
    PlantillaCuentas(
        id="vacio",
        nombre="Plan de cuentas vacío",
        descripcion="Empieza sin cuentas y crea las tuyas desde el Plan de Cuentas.",
        cuentas=[],
    ),
]

OPCIONES_PLANTILLA = [(plantilla.id, plantilla.nombre) for plantilla in PLANTILLAS_CUENTAS]


def obtener_plantilla(id_plantilla: str) -> PlantillaCuentas:
    for plantilla in PLANTILLAS_CUENTAS:
        if plantilla.id == id_plantilla:
            return plantilla
    return PLANTILLAS_CUENTAS[0]
