"""Balance de Comprobación: sumas y saldos por cuenta.

Está cuadrado cuando el total del Debe iguala al del Haber y el total deudor
iguala al acreedor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List

from .cuentas import indice_por_id, ordenar_cuentas
from .numeros import redondear, son_iguales, sumar
from .tipos import Caso, Cuenta

CERO = Decimal("0.00")


@dataclass
class FilaBalance:
    cuenta: Cuenta
    suma_debe: Decimal
    suma_haber: Decimal
    saldo_deudor: Decimal
    saldo_acreedor: Decimal


@dataclass
class BalanceComprobacion:
    filas: List[FilaBalance] = field(default_factory=list)
    total_debe: Decimal = CERO
    total_haber: Decimal = CERO
    total_deudor: Decimal = CERO
    total_acreedor: Decimal = CERO
    cuadrado: bool = True
    diferencia_sumas: Decimal = CERO
    diferencia_saldos: Decimal = CERO


def construir_balance_comprobacion(caso: Caso) -> BalanceComprobacion:
    cuentas_por_id = indice_por_id(caso.cuentas)
    sumas: Dict[str, List[Decimal]] = {}

    for asiento in caso.asientos:
        for linea in asiento.lineas:
            if linea.cuenta_id not in cuentas_por_id:
                continue
            actual = sumas.setdefault(linea.cuenta_id, [CERO, CERO])
            actual[0] = redondear(actual[0] + linea.debe)
            actual[1] = redondear(actual[1] + linea.haber)

    filas: List[FilaBalance] = []
    for cuenta in ordenar_cuentas(caso.cuentas):
        if cuenta.id not in sumas:
            continue
        debe, haber = sumas[cuenta.id]
        diferencia = redondear(debe - haber)
        filas.append(
            FilaBalance(
                cuenta=cuenta,
                suma_debe=debe,
                suma_haber=haber,
                saldo_deudor=diferencia if diferencia > 0 else CERO,
                saldo_acreedor=abs(diferencia) if diferencia < 0 else CERO,
            )
        )

    total_debe = sumar(fila.suma_debe for fila in filas)
    total_haber = sumar(fila.suma_haber for fila in filas)
    total_deudor = sumar(fila.saldo_deudor for fila in filas)
    total_acreedor = sumar(fila.saldo_acreedor for fila in filas)

    return BalanceComprobacion(
        filas=filas,
        total_debe=total_debe,
        total_haber=total_haber,
        total_deudor=total_deudor,
        total_acreedor=total_acreedor,
        cuadrado=son_iguales(total_debe, total_haber) and son_iguales(total_deudor, total_acreedor),
        diferencia_sumas=redondear(total_debe - total_haber),
        diferencia_saldos=redondear(total_deudor - total_acreedor),
    )
