"""Utilidades numéricas. Todo el dinero se redondea a 2 decimales.

Se usa Decimal en vez de float: es la aritmética correcta para dinero y evita
los errores de coma flotante que en la versión JavaScript obligaban a redondear
en cada paso.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

TOLERANCIA = Decimal("0.005")
CERO = Decimal("0.00")


def redondear(valor, decimales: int = 2) -> Decimal:
    """Redondea a `decimales` con redondeo comercial (0.005 sube)."""
    numero = a_numero(valor)
    cuantia = Decimal(1).scaleb(-decimales)
    return numero.quantize(cuantia, rounding=ROUND_HALF_UP)


def son_iguales(a, b, tolerancia: Decimal = TOLERANCIA) -> bool:
    return abs(a_numero(a) - a_numero(b)) < tolerancia


def es_cero(valor, tolerancia: Decimal = TOLERANCIA) -> bool:
    return abs(a_numero(valor)) < tolerancia


def sumar(valores: Iterable) -> Decimal:
    total = CERO
    for valor in valores:
        total += a_numero(valor)
    return redondear(total)


def a_numero(texto) -> Decimal:
    """Convierte texto de formulario a Decimal.

    Acepta coma decimal y separadores de miles; lo que no se entiende vale 0.
    """
    if isinstance(texto, Decimal):
        return texto if texto.is_finite() else CERO
    if isinstance(texto, bool) or texto is None:
        return CERO
    if isinstance(texto, int):
        return Decimal(texto)
    if isinstance(texto, float):
        return Decimal(str(texto))
    limpio = str(texto).strip().replace(" ", "").replace(",", "")
    if limpio == "":
        return CERO
    try:
        numero = Decimal(limpio)
    except InvalidOperation:
        return CERO
    return numero if numero.is_finite() else CERO
