"""Reglas sobre las cuentas: rubros válidos, naturaleza, orden y validación."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional

from .tipos import Cuenta, Rubro, TipoCuenta

TIPOS_CUENTA: List[TipoCuenta] = [
    TipoCuenta.ACTIVO,
    TipoCuenta.PASIVO,
    TipoCuenta.PATRIMONIO,
    TipoCuenta.INGRESO,
    TipoCuenta.GASTO,
]

ETIQUETA_TIPO: Dict[TipoCuenta, str] = {
    TipoCuenta.ACTIVO: "Activo",
    TipoCuenta.PASIVO: "Pasivo",
    TipoCuenta.PATRIMONIO: "Patrimonio",
    TipoCuenta.INGRESO: "Ingreso",
    TipoCuenta.GASTO: "Gasto",
}

ETIQUETA_RUBRO: Dict[Rubro, str] = {
    Rubro.CORRIENTE: "Corriente",
    Rubro.NO_CORRIENTE: "No corriente",
    Rubro.VENTAS: "Ventas",
    Rubro.DEVOLUCIONES_VENTAS: "Devoluciones sobre ventas",
    Rubro.DESCUENTOS_VENTAS: "Descuentos sobre ventas",
    Rubro.COSTO_VENTAS: "Costo de ventas",
    Rubro.GASTO_VENTAS: "Gasto de ventas",
    Rubro.GASTO_ADMINISTRACION: "Gasto de administración",
    Rubro.INGRESO_FINANCIERO: "Ingreso financiero",
    Rubro.GASTO_FINANCIERO: "Gasto financiero",
    Rubro.OTRO_INGRESO: "Otro ingreso",
    Rubro.OTRO_GASTO: "Otro gasto",
}

RUBROS_BALANCE = [Rubro.CORRIENTE, Rubro.NO_CORRIENTE]

RUBROS_INGRESO = [
    Rubro.VENTAS,
    Rubro.DEVOLUCIONES_VENTAS,
    Rubro.DESCUENTOS_VENTAS,
    Rubro.INGRESO_FINANCIERO,
    Rubro.OTRO_INGRESO,
]

RUBROS_GASTO = [
    Rubro.COSTO_VENTAS,
    Rubro.GASTO_VENTAS,
    Rubro.GASTO_ADMINISTRACION,
    Rubro.GASTO_FINANCIERO,
    Rubro.OTRO_GASTO,
]

REGEX_CODIGO = re.compile(r"^[A-Za-z0-9.-]+$")


def rubros_permitidos(tipo: TipoCuenta) -> List[Rubro]:
    """Rubros válidos para cada tipo de cuenta. El patrimonio no usa rubro."""
    if tipo in (TipoCuenta.ACTIVO, TipoCuenta.PASIVO):
        return list(RUBROS_BALANCE)
    if tipo == TipoCuenta.INGRESO:
        return list(RUBROS_INGRESO)
    if tipo == TipoCuenta.GASTO:
        return list(RUBROS_GASTO)
    return []


def rubro_por_defecto(tipo: TipoCuenta) -> Optional[Rubro]:
    """Rubro que se asume cuando la cuenta no declara uno."""
    if tipo in (TipoCuenta.ACTIVO, TipoCuenta.PASIVO):
        return Rubro.CORRIENTE
    if tipo == TipoCuenta.INGRESO:
        return Rubro.VENTAS
    if tipo == TipoCuenta.GASTO:
        return Rubro.GASTO_ADMINISTRACION
    return None


def rubro_efectivo(cuenta: Cuenta) -> Optional[Rubro]:
    if cuenta.rubro and cuenta.rubro in rubros_permitidos(cuenta.tipo):
        return cuenta.rubro
    return rubro_por_defecto(cuenta.tipo)


def es_naturaleza_deudora(tipo: TipoCuenta) -> bool:
    """Las cuentas de activo y de gasto son deudoras."""
    return tipo in (TipoCuenta.ACTIVO, TipoCuenta.GASTO)


def movimiento_desde_signo(tipo: TipoCuenta, signo: str, monto: Decimal):
    """Modo simple de registro (+ / -), tal como aparece en las diapositivas.

    Un "+" aumenta la cuenta: va al Debe si su naturaleza es deudora, al Haber
    si no. Devuelve (debe, haber).
    """
    aumenta = signo == "+"
    al_debe = aumenta if es_naturaleza_deudora(tipo) else not aumenta
    return (monto, Decimal("0")) if al_debe else (Decimal("0"), monto)


def etiqueta_cuenta(cuenta: Optional[Cuenta]) -> str:
    if cuenta is None:
        return "Cuenta desconocida"
    return f"{cuenta.codigo} — {cuenta.nombre}"


def clave_orden(cuenta: Cuenta):
    """Orden estable por código: numérico cuando se puede, alfabético si no."""
    try:
        numero = Decimal(cuenta.codigo)
        return (0, numero, "", _sin_tildes(cuenta.nombre))
    except (InvalidOperation, ValueError):
        return (1, Decimal(0), _sin_tildes(cuenta.codigo), _sin_tildes(cuenta.nombre))


def ordenar_cuentas(cuentas: Iterable[Cuenta]) -> List[Cuenta]:
    return sorted(cuentas, key=clave_orden)


def indice_por_id(cuentas: Iterable[Cuenta]) -> Dict[str, Cuenta]:
    return {cuenta.id: cuenta for cuenta in cuentas}


def validar_cuenta(codigo: str, nombre: str, tipo, cuentas_existentes, id_en_edicion=None):
    """Valida una cuenta antes de guardarla.

    Devuelve un diccionario vacío cuando todo está bien; si no, un mensaje por
    campo ("codigo", "nombre", "tipo").
    """
    errores = {}
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()

    if codigo == "":
        errores["codigo"] = "Escribe el código de la cuenta."
    elif len(codigo) > 12:
        errores["codigo"] = "El código admite hasta 12 caracteres."
    elif not REGEX_CODIGO.match(codigo):
        errores["codigo"] = "Usa solo letras, números, punto o guion."
    elif any(
        cuenta.id != id_en_edicion and cuenta.codigo.upper() == codigo.upper()
        for cuenta in cuentas_existentes
    ):
        errores["codigo"] = "Ya existe una cuenta con ese código."

    if nombre == "":
        errores["nombre"] = "Escribe el nombre de la cuenta."
    elif len(nombre) > 80:
        errores["nombre"] = "El nombre admite hasta 80 caracteres."

    try:
        TipoCuenta(tipo)
    except ValueError:
        errores["tipo"] = "Elige un tipo de cuenta."

    return errores


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto or "")
    return "".join(letra for letra in descompuesto if not unicodedata.combining(letra)).lower()
