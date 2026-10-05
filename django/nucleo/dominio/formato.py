"""Formato de números, moneda y fechas, con la convención peruana."""

from datetime import date

from .numeros import redondear

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
]


def formatear_numero(valor) -> str:
    """1234.5 -> "1,234.50" """
    return f"{redondear(valor):,.2f}"


def formatear_moneda(valor, simbolo: str = "S/") -> str:
    """1234.5 -> "S/ 1,234.50". El símbolo viene de la configuración del caso."""
    numero = redondear(valor)
    signo = "-" if numero < 0 else ""
    return f"{signo}{simbolo} {abs(numero):,.2f}"


def formatear_fecha(valor) -> str:
    """date(2024, 10, 1) o "2024-10-01" -> "01/10/2024"."""
    fecha = _a_fecha(valor)
    if fecha is None:
        return str(valor or "")
    return f"{fecha.day:02d}/{fecha.month:02d}/{fecha.year}"


def formatear_fecha_larga(valor) -> str:
    fecha = _a_fecha(valor)
    if fecha is None:
        return str(valor or "")
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def hoy() -> date:
    return date.today()


def _a_fecha(valor):
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None
