"""Libro Mayor: movimientos y saldos agrupados por cuenta y por tipo."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List

from .asientos import ordenar_asientos
from .cuentas import (
    ETIQUETA_TIPO,
    TIPOS_CUENTA,
    es_naturaleza_deudora,
    indice_por_id,
    ordenar_cuentas,
)
from .numeros import redondear, sumar
from .tipos import Caso, Cuenta, Naturaleza, TipoCuenta


@dataclass
class MovimientoMayor:
    fecha: object
    numero: int
    glosa: str
    debe: Decimal
    haber: Decimal
    #: Saldo acumulado, positivo en la naturaleza de la cuenta.
    saldo: Decimal


@dataclass
class CuentaMayor:
    cuenta: Cuenta
    movimientos: List[MovimientoMayor]
    total_debe: Decimal
    total_haber: Decimal
    saldo: Decimal
    naturaleza_saldo: Naturaleza


@dataclass
class GrupoMayor:
    tipo: TipoCuenta
    etiqueta: str
    cuentas: List[CuentaMayor]
    total_debe: Decimal
    total_haber: Decimal


@dataclass
class LibroMayor:
    grupos: List[GrupoMayor] = field(default_factory=list)
    total_debe: Decimal = Decimal("0.00")
    total_haber: Decimal = Decimal("0.00")


def construir_libro_mayor(caso: Caso) -> LibroMayor:
    cuentas_por_id = indice_por_id(caso.cuentas)
    acumulado: Dict[str, List[MovimientoMayor]] = {}

    for asiento in ordenar_asientos(caso.asientos):
        for linea in asiento.lineas:
            cuenta = cuentas_por_id.get(linea.cuenta_id)
            if cuenta is None:
                continue
            lista = acumulado.setdefault(cuenta.id, [])
            deudora = es_naturaleza_deudora(cuenta.tipo)
            anterior = lista[-1].saldo if lista else Decimal("0")
            efecto = linea.debe - linea.haber if deudora else linea.haber - linea.debe
            lista.append(
                MovimientoMayor(
                    fecha=asiento.fecha,
                    numero=asiento.numero,
                    glosa=asiento.glosa,
                    debe=linea.debe,
                    haber=linea.haber,
                    saldo=redondear(anterior + efecto),
                )
            )

    grupos: List[GrupoMayor] = []
    for tipo in TIPOS_CUENTA:
        del_tipo = ordenar_cuentas(
            cuenta for cuenta in caso.cuentas if cuenta.tipo == tipo and acumulado.get(cuenta.id)
        )
        cuentas: List[CuentaMayor] = []
        for cuenta in del_tipo:
            movimientos = acumulado[cuenta.id]
            total_debe = sumar(movimiento.debe for movimiento in movimientos)
            total_haber = sumar(movimiento.haber for movimiento in movimientos)
            diferencia = redondear(total_debe - total_haber)
            cuentas.append(
                CuentaMayor(
                    cuenta=cuenta,
                    movimientos=movimientos,
                    total_debe=total_debe,
                    total_haber=total_haber,
                    saldo=abs(diferencia),
                    naturaleza_saldo=Naturaleza.DEUDOR if diferencia >= 0 else Naturaleza.ACREEDOR,
                )
            )
        if not cuentas:
            continue
        grupos.append(
            GrupoMayor(
                tipo=tipo,
                etiqueta=ETIQUETA_TIPO[tipo],
                cuentas=cuentas,
                total_debe=sumar(item.total_debe for item in cuentas),
                total_haber=sumar(item.total_haber for item in cuentas),
            )
        )

    return LibroMayor(
        grupos=grupos,
        total_debe=sumar(grupo.total_debe for grupo in grupos),
        total_haber=sumar(grupo.total_haber for grupo in grupos),
    )
