"""Estado de Resultados: de las ventas a la utilidad neta."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .cuentas import ETIQUETA_RUBRO, indice_por_id, ordenar_cuentas, rubro_efectivo
from .numeros import redondear, sumar
from .tipos import Caso, Cuenta, Rubro, TipoCuenta

CERO = Decimal("0.00")

RUBROS: List[Rubro] = [
    Rubro.VENTAS,
    Rubro.DEVOLUCIONES_VENTAS,
    Rubro.DESCUENTOS_VENTAS,
    Rubro.COSTO_VENTAS,
    Rubro.GASTO_VENTAS,
    Rubro.GASTO_ADMINISTRACION,
    Rubro.INGRESO_FINANCIERO,
    Rubro.GASTO_FINANCIERO,
    Rubro.OTRO_INGRESO,
    Rubro.OTRO_GASTO,
]


@dataclass
class DetalleCuentaResultado:
    cuenta: Cuenta
    monto: Decimal


@dataclass
class SeccionResultado:
    rubro: Rubro
    etiqueta: str
    cuentas: List[DetalleCuentaResultado]
    total: Decimal


@dataclass
class FilaResultado:
    clave: str
    etiqueta: str
    monto: Decimal
    #: "detalle", "subtotal" o "total": decide el estilo de la fila.
    clase: str
    #: "-" cuando la línea resta en el reporte. Solo afecta la presentación.
    signo: Optional[str] = None


@dataclass
class EstadoResultados:
    secciones: Dict[Rubro, SeccionResultado] = field(default_factory=dict)
    filas: List[FilaResultado] = field(default_factory=list)
    ventas: Decimal = CERO
    devoluciones: Decimal = CERO
    descuentos: Decimal = CERO
    ventas_netas: Decimal = CERO
    costo_ventas: Decimal = CERO
    utilidad_bruta: Decimal = CERO
    gasto_ventas: Decimal = CERO
    gasto_administracion: Decimal = CERO
    utilidad_operativa: Decimal = CERO
    ingresos_financieros: Decimal = CERO
    gastos_financieros: Decimal = CERO
    otros_ingresos: Decimal = CERO
    otros_gastos: Decimal = CERO
    resultado_antes_impuesto: Decimal = CERO
    tasa_impuesto: Decimal = CERO
    impuesto: Decimal = CERO
    utilidad_neta: Decimal = CERO
    total_ingresos: Decimal = CERO
    total_gastos: Decimal = CERO


def _saldos_de_resultado(caso: Caso) -> Dict[str, Decimal]:
    """Saldo de cada cuenta de resultados en positivo.

    Los ingresos acumulan en el Haber y los gastos en el Debe.
    """
    cuentas_por_id = indice_por_id(caso.cuentas)
    saldos: Dict[str, Decimal] = {}
    for asiento in caso.asientos:
        for linea in asiento.lineas:
            cuenta = cuentas_por_id.get(linea.cuenta_id)
            if cuenta is None or cuenta.tipo not in (TipoCuenta.INGRESO, TipoCuenta.GASTO):
                continue
            efecto = (
                linea.haber - linea.debe
                if cuenta.tipo == TipoCuenta.INGRESO
                else linea.debe - linea.haber
            )
            saldos[cuenta.id] = redondear(saldos.get(cuenta.id, CERO) + efecto)
    return saldos


def construir_estado_resultados(caso: Caso) -> EstadoResultados:
    saldos = _saldos_de_resultado(caso)
    ordenadas = ordenar_cuentas(caso.cuentas)

    secciones: Dict[Rubro, SeccionResultado] = {}
    for rubro in RUBROS:
        cuentas = [
            DetalleCuentaResultado(cuenta=cuenta, monto=saldos[cuenta.id])
            for cuenta in ordenadas
            if cuenta.id in saldos and rubro_efectivo(cuenta) == rubro
        ]
        secciones[rubro] = SeccionResultado(
            rubro=rubro,
            etiqueta=ETIQUETA_RUBRO[rubro],
            cuentas=cuentas,
            total=sumar(item.monto for item in cuentas),
        )

    ventas = secciones[Rubro.VENTAS].total
    devoluciones = secciones[Rubro.DEVOLUCIONES_VENTAS].total
    descuentos = secciones[Rubro.DESCUENTOS_VENTAS].total
    ventas_netas = redondear(ventas - devoluciones - descuentos)
    costo_ventas = secciones[Rubro.COSTO_VENTAS].total
    utilidad_bruta = redondear(ventas_netas - costo_ventas)
    gasto_ventas = secciones[Rubro.GASTO_VENTAS].total
    gasto_administracion = secciones[Rubro.GASTO_ADMINISTRACION].total
    utilidad_operativa = redondear(utilidad_bruta - gasto_ventas - gasto_administracion)
    ingresos_financieros = secciones[Rubro.INGRESO_FINANCIERO].total
    gastos_financieros = secciones[Rubro.GASTO_FINANCIERO].total
    otros_ingresos = secciones[Rubro.OTRO_INGRESO].total
    otros_gastos = secciones[Rubro.OTRO_GASTO].total
    resultado_antes_impuesto = redondear(
        utilidad_operativa
        + ingresos_financieros
        - gastos_financieros
        + otros_ingresos
        - otros_gastos
    )

    tasa_impuesto = max(Decimal("0"), caso.empresa.tasa_impuesto_renta or Decimal("0"))
    impuesto = (
        redondear(resultado_antes_impuesto * tasa_impuesto / Decimal("100"))
        if resultado_antes_impuesto > 0
        else CERO
    )
    utilidad_neta = redondear(resultado_antes_impuesto - impuesto)

    filas = [
        FilaResultado("ventas", "Ventas", ventas, "detalle"),
        FilaResultado("devoluciones", "Devoluciones sobre ventas", devoluciones, "detalle", "-"),
        FilaResultado("descuentos", "Descuentos sobre ventas", descuentos, "detalle", "-"),
        FilaResultado("ventasNetas", "Ventas netas", ventas_netas, "subtotal"),
        FilaResultado("costoVentas", "Costo de ventas", costo_ventas, "detalle", "-"),
        FilaResultado("utilidadBruta", "Utilidad bruta", utilidad_bruta, "subtotal"),
        FilaResultado("gastoVentas", "Gastos de ventas", gasto_ventas, "detalle", "-"),
        FilaResultado(
            "gastoAdministracion", "Gastos de administración", gasto_administracion, "detalle", "-"
        ),
        FilaResultado("utilidadOperativa", "Utilidad operativa", utilidad_operativa, "subtotal"),
        FilaResultado("ingresosFinancieros", "Ingresos financieros", ingresos_financieros, "detalle"),
        FilaResultado("gastosFinancieros", "Gastos financieros", gastos_financieros, "detalle", "-"),
        FilaResultado("otrosIngresos", "Otros ingresos", otros_ingresos, "detalle"),
        FilaResultado("otrosGastos", "Otros gastos", otros_gastos, "detalle", "-"),
        FilaResultado(
            "resultadoAntesImpuesto",
            "Resultado antes del impuesto a la renta",
            resultado_antes_impuesto,
            "subtotal",
        ),
        FilaResultado(
            "impuesto",
            f"Impuesto a la renta ({_porcentaje(tasa_impuesto)}%)",
            impuesto,
            "detalle",
            "-",
        ),
        FilaResultado("utilidadNeta", "Utilidad neta", utilidad_neta, "total"),
    ]

    total_ingresos = sumar([ventas, ingresos_financieros, otros_ingresos, -devoluciones, -descuentos])
    total_gastos = sumar(
        [costo_ventas, gasto_ventas, gasto_administracion, gastos_financieros, otros_gastos]
    )

    return EstadoResultados(
        secciones=secciones,
        filas=filas,
        ventas=ventas,
        devoluciones=devoluciones,
        descuentos=descuentos,
        ventas_netas=ventas_netas,
        costo_ventas=costo_ventas,
        utilidad_bruta=utilidad_bruta,
        gasto_ventas=gasto_ventas,
        gasto_administracion=gasto_administracion,
        utilidad_operativa=utilidad_operativa,
        ingresos_financieros=ingresos_financieros,
        gastos_financieros=gastos_financieros,
        otros_ingresos=otros_ingresos,
        otros_gastos=otros_gastos,
        resultado_antes_impuesto=resultado_antes_impuesto,
        tasa_impuesto=tasa_impuesto,
        impuesto=impuesto,
        utilidad_neta=utilidad_neta,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
    )


def _porcentaje(tasa: Decimal) -> str:
    """30 -> "30"; 18.5 -> "18.5". Sin ceros de relleno en la etiqueta."""
    texto = f"{redondear(tasa):f}".rstrip("0").rstrip(".")
    return texto or "0"
