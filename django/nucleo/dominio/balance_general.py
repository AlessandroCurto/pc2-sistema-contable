"""Balance General (Estado de Situación Financiera).

El resultado del ejercicio sale del Estado de Resultados y se suma al
patrimonio, porque las cuentas de ingreso y gasto se cierran contra él.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .cuentas import indice_por_id, ordenar_cuentas, rubro_efectivo
from .estado_resultados import construir_estado_resultados
from .numeros import redondear, son_iguales, sumar
from .tipos import Caso, Cuenta, Rubro, TipoCuenta

CERO = Decimal("0.00")


@dataclass
class DetalleCuentaBalance:
    cuenta: Cuenta
    monto: Decimal


@dataclass
class BloqueBalance:
    clave: str
    etiqueta: str
    cuentas: List[DetalleCuentaBalance] = field(default_factory=list)
    total: Decimal = CERO


@dataclass
class BalanceGeneral:
    activo_corriente: BloqueBalance
    activo_no_corriente: BloqueBalance
    pasivo_corriente: BloqueBalance
    pasivo_no_corriente: BloqueBalance
    patrimonio: BloqueBalance
    total_activo: Decimal
    total_pasivo: Decimal
    total_patrimonio_aportado: Decimal
    resultado_ejercicio: Decimal
    total_patrimonio: Decimal
    total_pasivo_patrimonio: Decimal
    diferencia: Decimal
    cuadrado: bool
    #: True cuando el resultado del ejercicio ya está neto de impuesto a la renta.
    resultado_neto_de_impuesto: bool


def _bloque(clave: str, etiqueta: str, cuentas: List[DetalleCuentaBalance]) -> BloqueBalance:
    return BloqueBalance(
        clave=clave,
        etiqueta=etiqueta,
        cuentas=cuentas,
        total=sumar(item.monto for item in cuentas),
    )


def construir_balance_general(caso: Caso) -> BalanceGeneral:
    cuentas_por_id = indice_por_id(caso.cuentas)
    saldos: Dict[str, Decimal] = {}

    for asiento in caso.asientos:
        for linea in asiento.lineas:
            cuenta = cuentas_por_id.get(linea.cuenta_id)
            if cuenta is None or cuenta.tipo in (TipoCuenta.INGRESO, TipoCuenta.GASTO):
                continue
            efecto = (
                linea.debe - linea.haber
                if cuenta.tipo == TipoCuenta.ACTIVO
                else linea.haber - linea.debe
            )
            saldos[cuenta.id] = redondear(saldos.get(cuenta.id, CERO) + efecto)

    ordenadas = [cuenta for cuenta in ordenar_cuentas(caso.cuentas) if cuenta.id in saldos]

    def tomar(tipo: TipoCuenta, rubro: Optional[Rubro] = None) -> List[DetalleCuentaBalance]:
        return [
            DetalleCuentaBalance(cuenta=cuenta, monto=saldos[cuenta.id])
            for cuenta in ordenadas
            if cuenta.tipo == tipo and (rubro is None or rubro_efectivo(cuenta) == rubro)
        ]

    activo_corriente = _bloque(
        "activoCorriente", "Activo corriente", tomar(TipoCuenta.ACTIVO, Rubro.CORRIENTE)
    )
    activo_no_corriente = _bloque(
        "activoNoCorriente", "Activo no corriente", tomar(TipoCuenta.ACTIVO, Rubro.NO_CORRIENTE)
    )
    pasivo_corriente = _bloque(
        "pasivoCorriente", "Pasivo corriente", tomar(TipoCuenta.PASIVO, Rubro.CORRIENTE)
    )
    pasivo_no_corriente = _bloque(
        "pasivoNoCorriente", "Pasivo no corriente", tomar(TipoCuenta.PASIVO, Rubro.NO_CORRIENTE)
    )
    patrimonio = _bloque("patrimonio", "Patrimonio", tomar(TipoCuenta.PATRIMONIO))

    estado = construir_estado_resultados(caso)
    resultado_neto_de_impuesto = caso.empresa.impuesto_afecta_patrimonio is True
    resultado_ejercicio = (
        estado.utilidad_neta if resultado_neto_de_impuesto else estado.resultado_antes_impuesto
    )

    total_activo = redondear(activo_corriente.total + activo_no_corriente.total)
    total_pasivo = redondear(pasivo_corriente.total + pasivo_no_corriente.total)
    total_patrimonio = redondear(patrimonio.total + resultado_ejercicio)
    total_pasivo_patrimonio = redondear(total_pasivo + total_patrimonio)

    return BalanceGeneral(
        activo_corriente=activo_corriente,
        activo_no_corriente=activo_no_corriente,
        pasivo_corriente=pasivo_corriente,
        pasivo_no_corriente=pasivo_no_corriente,
        patrimonio=patrimonio,
        total_activo=total_activo,
        total_pasivo=total_pasivo,
        total_patrimonio_aportado=patrimonio.total,
        resultado_ejercicio=resultado_ejercicio,
        total_patrimonio=total_patrimonio,
        total_pasivo_patrimonio=total_pasivo_patrimonio,
        diferencia=redondear(total_activo - total_pasivo_patrimonio),
        cuadrado=son_iguales(total_activo, total_pasivo_patrimonio),
        resultado_neto_de_impuesto=resultado_neto_de_impuesto,
    )
