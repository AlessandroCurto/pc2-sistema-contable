"""Tipos del dominio contable. Todo el motor trabaja sobre estas estructuras.

Son dataclasses puras: no importan Django ni la base de datos, así se pueden
probar solas y los modelos solo tienen que convertirse a ellas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class TipoCuenta(str, Enum):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PATRIMONIO = "PATRIMONIO"
    INGRESO = "INGRESO"
    GASTO = "GASTO"


class Rubro(str, Enum):
    """Clasificación de la cuenta.

    CORRIENTE y NO_CORRIENTE las usa el Balance General; las demás, el Estado
    de Resultados.
    """

    CORRIENTE = "CORRIENTE"
    NO_CORRIENTE = "NO_CORRIENTE"
    VENTAS = "VENTAS"
    DEVOLUCIONES_VENTAS = "DEVOLUCIONES_VENTAS"
    DESCUENTOS_VENTAS = "DESCUENTOS_VENTAS"
    COSTO_VENTAS = "COSTO_VENTAS"
    GASTO_VENTAS = "GASTO_VENTAS"
    GASTO_ADMINISTRACION = "GASTO_ADMINISTRACION"
    INGRESO_FINANCIERO = "INGRESO_FINANCIERO"
    GASTO_FINANCIERO = "GASTO_FINANCIERO"
    OTRO_INGRESO = "OTRO_INGRESO"
    OTRO_GASTO = "OTRO_GASTO"


class Naturaleza(str, Enum):
    DEUDOR = "DEUDOR"
    ACREEDOR = "ACREEDOR"


@dataclass(frozen=True)
class Cuenta:
    id: str
    codigo: str
    nombre: str
    tipo: TipoCuenta
    rubro: Optional[Rubro] = None


@dataclass(frozen=True)
class LineaAsiento:
    id: str
    cuenta_id: str
    debe: Decimal
    haber: Decimal


@dataclass(frozen=True)
class Asiento:
    id: str
    numero: int
    fecha: date
    glosa: str
    lineas: List[LineaAsiento] = field(default_factory=list)


@dataclass(frozen=True)
class Empresa:
    nombre: str
    ruc: str = ""
    simbolo_moneda: str = "S/"
    periodo_inicio: Optional[date] = None
    periodo_fin: Optional[date] = None
    #: Porcentaje de impuesto a la renta aplicado en el Estado de Resultados.
    tasa_impuesto_renta: Decimal = Decimal("0")
    #: Si es True, el Balance General resta el impuesto del resultado del
    #: ejercicio. Por omisión False: el impuesto no se registra como asiento,
    #: así que el patrimonio muestra la utilidad antes de impuestos.
    impuesto_afecta_patrimonio: bool = False


@dataclass(frozen=True)
class Caso:
    id: str
    nombre: str
    empresa: Empresa
    cuentas: List[Cuenta] = field(default_factory=list)
    asientos: List[Asiento] = field(default_factory=list)
