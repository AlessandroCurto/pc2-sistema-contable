"""Casos de ejemplo. Son solo datos: la lógica de los reportes no depende de ellos.

Sirven para comprobar el sistema y para las pruebas automáticas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from .plantillas_cuentas import obtener_plantilla


@dataclass(frozen=True)
class LineaDemo:
    codigo: str
    debe: Decimal = Decimal("0")
    haber: Decimal = Decimal("0")


@dataclass(frozen=True)
class AsientoDemo:
    fecha: date
    glosa: str
    lineas: List[LineaDemo]


@dataclass(frozen=True)
class PlantillaCaso:
    id: str
    nombre: str
    descripcion: str
    plantilla_cuentas: str
    razon_social: str
    ruc: str
    simbolo_moneda: str
    periodo_inicio: date
    periodo_fin: date
    tasa_impuesto_renta: Decimal
    impuesto_afecta_patrimonio: bool
    asientos: List[AsientoDemo]


def _d(valor) -> Decimal:
    return Decimal(str(valor))


def _debe(codigo: str, monto) -> LineaDemo:
    return LineaDemo(codigo=codigo, debe=_d(monto))


def _haber(codigo: str, monto) -> LineaDemo:
    return LineaDemo(codigo=codigo, haber=_d(monto))


CYBERTEC = PlantillaCaso(
    id="cybertec",
    nombre="CYBERTEC S.A.",
    descripcion=(
        "Constitución con aportes, compra de mercadería, venta al contado y ajuste "
        "del costo de ventas."
    ),
    plantilla_cuentas="pcge",
    razon_social="CYBERTEC S.A.",
    ruc="20100000001",
    simbolo_moneda="S/",
    periodo_inicio=date(2024, 10, 1),
    periodo_fin=date(2024, 10, 31),
    tasa_impuesto_renta=Decimal("0"),
    impuesto_afecta_patrimonio=False,
    asientos=[
        AsientoDemo(
            fecha=date(2024, 10, 1),
            glosa="Constitución de la empresa: aporte en efectivo y en equipos de cómputo",
            lineas=[_debe("10", 20000), _debe("33", 30000), _haber("50", 50000)],
        ),
        AsientoDemo(
            fecha=date(2024, 10, 10),
            glosa="Compra de mercadería por 20,000",
            lineas=[_debe("20", 20000), _haber("10", 20000)],
        ),
        AsientoDemo(
            fecha=date(2024, 10, 20),
            glosa="Venta al contado por 20,000",
            lineas=[_debe("10", 20000), _haber("70", 20000)],
        ),
        AsientoDemo(
            fecha=date(2024, 10, 30),
            glosa="Ajuste por costo de ventas; el inventario cierra en 10,000",
            lineas=[_debe("69", 10000), _haber("20", 10000)],
        ),
    ],
)

METROPOLITANA = PlantillaCaso(
    id="metropolitana",
    nombre="Comercializadora Metropolitana",
    descripcion=(
        "Saldos iniciales, compra con letras e IGV, venta mixta, arriendo, pagos y "
        "cobros de letras."
    ),
    plantilla_cuentas="numerado",
    razon_social="Comercializadora Metropolitana",
    ruc="20100000002",
    simbolo_moneda="S/",
    periodo_inicio=date(2023, 6, 1),
    periodo_fin=date(2023, 6, 30),
    tasa_impuesto_renta=Decimal("30"),
    impuesto_afecta_patrimonio=False,
    asientos=[
        AsientoDemo(
            fecha=date(2023, 6, 1),
            glosa="Apertura de saldos iniciales",
            lineas=[
                _debe("101", 2500000),
                _debe("102", 3500000),
                _debe("103", 600000),
                _haber("201", 800000),
                _haber("301", 5800000),
            ],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 1),
            glosa="Compra a Adelco Ltda. con 10 letras de cambio",
            lineas=[_debe("105", 840336), _debe("106", 159664), _haber("202", 1000000)],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 2),
            glosa="Venta a Mario Cea Castro: 40% en efectivo y 60% en letras",
            lineas=[
                _debe("101", 190400),
                _debe("104", 285600),
                _haber("401", 400000),
                _haber("203", 76000),
            ],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 10),
            glosa="Pago del arriendo de oficina con cheque",
            lineas=[_debe("501", 100000), _haber("102", 100000)],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 11),
            glosa="Pago del 50% de la deuda a proveedores con cheque",
            lineas=[_debe("201", 400000), _haber("102", 400000)],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 15),
            glosa="Cobro de las letras 101 y 102 a Mario Cea Castro",
            lineas=[_debe("101", 142800), _haber("104", 142800)],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 30),
            glosa="Pago de 3 letras a Adelco Ltda. con cheque",
            lineas=[_debe("202", 300000), _haber("102", 300000)],
        ),
        AsientoDemo(
            fecha=date(2023, 6, 30),
            glosa="Ajuste por costo de ventas; existencia final de mercaderías 690,360",
            lineas=[_debe("502", 149976), _haber("105", 149976)],
        ),
    ],
)

PLANTILLAS_CASO = [CYBERTEC, METROPOLITANA]

OPCIONES_CASO_DEMO = [(plantilla.id, plantilla.nombre) for plantilla in PLANTILLAS_CASO]


def obtener_plantilla_caso(id_caso: str) -> Optional[PlantillaCaso]:
    for plantilla in PLANTILLAS_CASO:
        if plantilla.id == id_caso:
            return plantilla
    return None


def crear_caso_demo(plantilla: PlantillaCaso):
    """Guarda el caso de ejemplo en la base de datos y lo devuelve.

    Se importa aquí y no arriba para que este módulo se pueda leer sin Django.
    """
    from django.db import transaction

    from ..models import Asiento, Caso, Cuenta, LineaAsiento

    definiciones = obtener_plantilla(plantilla.plantilla_cuentas).cuentas

    with transaction.atomic():
        caso = Caso.objects.create(
            nombre=plantilla.nombre,
            razon_social=plantilla.razon_social,
            ruc=plantilla.ruc,
            simbolo_moneda=plantilla.simbolo_moneda,
            periodo_inicio=plantilla.periodo_inicio,
            periodo_fin=plantilla.periodo_fin,
            tasa_impuesto_renta=plantilla.tasa_impuesto_renta,
            impuesto_afecta_patrimonio=plantilla.impuesto_afecta_patrimonio,
        )
        Cuenta.objects.bulk_create(
            Cuenta(
                caso=caso,
                codigo=definicion.codigo,
                nombre=definicion.nombre,
                tipo=definicion.tipo,
                rubro=definicion.rubro or "",
            )
            for definicion in definiciones
        )
        por_codigo = {cuenta.codigo: cuenta for cuenta in caso.cuentas.all()}

        for numero, demo in enumerate(plantilla.asientos, start=1):
            asiento = Asiento.objects.create(
                caso=caso, numero=numero, fecha=demo.fecha, glosa=demo.glosa
            )
            lineas = []
            for orden, linea in enumerate(demo.lineas):
                cuenta = por_codigo.get(linea.codigo)
                if cuenta is None:
                    raise ValueError(
                        "El caso " + plantilla.nombre + " usa la cuenta " + linea.codigo
                        + ", que no existe en su plan de cuentas."
                    )
                lineas.append(
                    LineaAsiento(
                        asiento=asiento,
                        cuenta=cuenta,
                        debe=linea.debe,
                        haber=linea.haber,
                        orden=orden,
                    )
                )
            LineaAsiento.objects.bulk_create(lineas)

    return caso
