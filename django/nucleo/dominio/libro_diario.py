"""Libro Diario: los asientos en orden cronológico, con sus líneas."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from .asientos import ordenar_asientos, resumir_asiento
from .cuentas import indice_por_id
from .numeros import sumar
from .tipos import Asiento, Caso, Cuenta, TipoCuenta


@dataclass
class FiltroDiario:
    desde: Optional[object] = None
    hasta: Optional[object] = None
    cuenta_id: str = ""
    texto: str = ""

    def vacio(self) -> bool:
        return not (self.desde or self.hasta or self.cuenta_id or self.texto.strip())


@dataclass
class FilaDiario:
    asiento_id: str
    numero: int
    fecha: object
    glosa: str
    cuenta: Optional[Cuenta]
    tipo: Optional[TipoCuenta]
    debe: Decimal
    haber: Decimal
    #: True en la primera línea del asiento: las plantillas solo repiten
    #: número, fecha y glosa una vez por asiento.
    primera: bool = False


@dataclass
class AsientoDiario:
    asiento: Asiento
    filas: List[FilaDiario]
    total_debe: Decimal
    total_haber: Decimal
    cuadrado: bool


@dataclass
class LibroDiario:
    asientos: List[AsientoDiario] = field(default_factory=list)
    filas: List[FilaDiario] = field(default_factory=list)
    total_debe: Decimal = Decimal("0.00")
    total_haber: Decimal = Decimal("0.00")


def _cumple_filtro(asiento: Asiento, filtro: FiltroDiario, cuentas) -> bool:
    if filtro.desde and asiento.fecha < filtro.desde:
        return False
    if filtro.hasta and asiento.fecha > filtro.hasta:
        return False
    if filtro.cuenta_id and not any(
        linea.cuenta_id == filtro.cuenta_id for linea in asiento.lineas
    ):
        return False
    texto = (filtro.texto or "").strip().lower()
    if texto:
        en_glosa = texto in asiento.glosa.lower()
        en_numero = str(asiento.numero) == texto
        en_cuentas = False
        for linea in asiento.lineas:
            cuenta = cuentas.get(linea.cuenta_id)
            if cuenta and (texto in cuenta.nombre.lower() or texto in cuenta.codigo.lower()):
                en_cuentas = True
                break
        if not (en_glosa or en_numero or en_cuentas):
            return False
    return True


def construir_libro_diario(caso: Caso, filtro: FiltroDiario = None) -> LibroDiario:
    filtro = filtro or FiltroDiario()
    cuentas = indice_por_id(caso.cuentas)
    asientos = [
        asiento
        for asiento in ordenar_asientos(caso.asientos)
        if _cumple_filtro(asiento, filtro, cuentas)
    ]

    detalle: List[AsientoDiario] = []
    for asiento in asientos:
        filas: List[FilaDiario] = []
        for indice, linea in enumerate(asiento.lineas):
            cuenta = cuentas.get(linea.cuenta_id)
            filas.append(
                FilaDiario(
                    asiento_id=asiento.id,
                    numero=asiento.numero,
                    fecha=asiento.fecha,
                    glosa=asiento.glosa,
                    cuenta=cuenta,
                    tipo=cuenta.tipo if cuenta else None,
                    debe=linea.debe,
                    haber=linea.haber,
                    primera=indice == 0,
                )
            )
        resumen = resumir_asiento(asiento.lineas)
        detalle.append(
            AsientoDiario(
                asiento=asiento,
                filas=filas,
                total_debe=resumen.total_debe,
                total_haber=resumen.total_haber,
                cuadrado=resumen.cuadrado,
            )
        )

    filas = [fila for item in detalle for fila in item.filas]
    return LibroDiario(
        asientos=detalle,
        filas=filas,
        total_debe=sumar(fila.debe for fila in filas),
        total_haber=sumar(fila.haber for fila in filas),
    )
