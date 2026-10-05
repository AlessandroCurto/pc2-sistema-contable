"""Validación y orden de los asientos. Aquí vive la regla central: Debe = Haber."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List

from .numeros import es_cero, redondear, son_iguales, sumar
from .tipos import Asiento, Cuenta, LineaAsiento


@dataclass
class ResumenAsiento:
    total_debe: Decimal
    total_haber: Decimal
    diferencia: Decimal
    cuadrado: bool


@dataclass
class ErroresAsiento:
    fecha: str = ""
    glosa: str = ""
    lineas: str = ""
    cuadre: str = ""
    por_linea: Dict[str, str] = None

    def __post_init__(self):
        if self.por_linea is None:
            self.por_linea = {}

    def hay_errores(self) -> bool:
        return bool(self.fecha or self.glosa or self.lineas or self.cuadre or self.por_linea)


def resumir_asiento(lineas: Iterable[LineaAsiento]) -> ResumenAsiento:
    lineas = list(lineas)
    total_debe = sumar(redondear(linea.debe) for linea in lineas)
    total_haber = sumar(redondear(linea.haber) for linea in lineas)
    return ResumenAsiento(
        total_debe=total_debe,
        total_haber=total_haber,
        diferencia=redondear(total_debe - total_haber),
        cuadrado=son_iguales(total_debe, total_haber) and not es_cero(total_debe),
    )


def validar_asiento(fecha, glosa: str, lineas: Iterable[LineaAsiento], cuentas: Iterable[Cuenta]):
    """Un asiento solo se guarda si el Debe iguala al Haber.

    Además cada línea necesita una cuenta existente y un único importe positivo.
    """
    errores = ErroresAsiento()
    ids_cuentas = {cuenta.id for cuenta in cuentas}

    if not isinstance(fecha, date):
        errores.fecha = "Elige una fecha válida."
    if len((glosa or "").strip()) > 140:
        errores.glosa = "La glosa admite hasta 140 caracteres."

    con_datos: List[LineaAsiento] = [
        linea
        for linea in lineas
        if linea.cuenta_id != "" or not es_cero(linea.debe) or not es_cero(linea.haber)
    ]

    if len(con_datos) < 2:
        errores.lineas = "Un asiento necesita al menos dos líneas con cuenta e importe."

    for linea in con_datos:
        if linea.cuenta_id == "" or linea.cuenta_id not in ids_cuentas:
            errores.por_linea[linea.id] = "Elige una cuenta del plan de cuentas."
            continue
        debe = redondear(linea.debe)
        haber = redondear(linea.haber)
        if debe < 0 or haber < 0:
            errores.por_linea[linea.id] = "Los importes no pueden ser negativos."
            continue
        if not es_cero(debe) and not es_cero(haber):
            errores.por_linea[linea.id] = "Escribe el importe en el Debe o en el Haber, no en ambos."
            continue
        if es_cero(debe) and es_cero(haber):
            errores.por_linea[linea.id] = "Escribe un importe mayor que cero."

    resumen = resumir_asiento(con_datos)
    if not errores.lineas and not errores.por_linea:
        if es_cero(resumen.total_debe) and es_cero(resumen.total_haber):
            errores.cuadre = "El asiento no tiene importes."
        elif not resumen.cuadrado:
            diferencia = redondear(abs(resumen.diferencia))
            errores.cuadre = f"El asiento no cuadra. Diferencia de {diferencia:.2f}."

    return errores


def normalizar_lineas(lineas: Iterable[LineaAsiento]) -> List[LineaAsiento]:
    """Quita líneas vacías y redondea importes antes de guardar."""
    return [
        LineaAsiento(
            id=linea.id,
            cuenta_id=linea.cuenta_id,
            debe=redondear(linea.debe),
            haber=redondear(linea.haber),
        )
        for linea in lineas
        if linea.cuenta_id != "" and (not es_cero(linea.debe) or not es_cero(linea.haber))
    ]


def clave_orden(asiento: Asiento):
    """Orden cronológico; a igual fecha manda el correlativo."""
    return (asiento.fecha, asiento.numero)


def ordenar_asientos(asientos: Iterable[Asiento]) -> List[Asiento]:
    return sorted(asientos, key=clave_orden)


def siguiente_numero(asientos: Iterable[Asiento]) -> int:
    return max((asiento.numero for asiento in asientos), default=0) + 1


def total_asiento(asiento: Asiento) -> Decimal:
    return resumir_asiento(asiento.lineas).total_debe
