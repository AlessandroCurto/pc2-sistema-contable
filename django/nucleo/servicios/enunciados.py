"""Lee un enunciado contable y propone los asientos.

Es la pieza que faltaba del asistente local: con esto resuelve un caso nuevo
sin llamar a ninguna API. No "entiende" el texto como lo haría un modelo de
lenguaje; reconoce el vocabulario con el que están escritos estos enunciados
(compra, venta, letras, arriendo, costo de ventas...) y hace la aritmética con
Decimal, así los asientos siempre cuadran al céntimo.

A cambio es honesto: la operación que no reconoce la informa en vez de
inventarla, y nunca propone un asiento descuadrado.

Lo que sí sabe hacer, y un modelo de lenguaje no, es mirar hacia atrás: el
valor de cada letra sale de la operación que las emitió, el 50% de la deuda
sale del saldo inicial de proveedores y el costo de ventas sale de las compras
que ya leyó.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ..dominio.tipos import Caso as CasoDominio
from ..dominio.tipos import Cuenta, Empresa, Rubro, TipoCuenta

IGV = Decimal("0.18")
UNO_MAS_IGV = Decimal("1.18")
CENTIMO = Decimal("0.01")


def _plano(texto: str) -> str:
    sin = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def _r(valor: Decimal) -> Decimal:
    return valor.quantize(CENTIMO)


def _n(valor: Decimal) -> str:
    return f"{valor:,.2f}"


# ------------------------------------------------------- el plan de cuentas

#: Qué palabras identifican a cada cuenta que el lector necesita.
PAPELES: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "caja": (("caja",), ("efectivo",)),
    "banco": (("banco",), ("cuenta corriente",)),
    "clientes": (("clientes",), ("cuentas por cobrar",)),
    "letras_cobrar": (("letras por cobrar",), ("documentos por cobrar",)),
    "mercaderias": (("mercader",), ("existencias",)),
    "igv_credito": (("igv", "credito"), ("credito fiscal",)),
    "igv_debito": (("igv", "debito"), ("debito fiscal",)),
    "proveedores": (("proveedores",), ("cuentas por pagar",)),
    "letras_pagar": (("letras por pagar",), ("documentos por pagar",)),
    "capital": (("capital",),),
    "ventas": (("ventas",),),
    "costo_ventas": (("costo de ventas",),),
    "arriendo": (("arriendo",), ("alquiler",)),
    "personal": (("personal",), ("sueldos",), ("remuneraciones",)),
    "servicios": (("servicios",),),
}

#: Si al plan de cuentas le falta una de estas, el asistente la puede crear.
#: Los códigos son los del plan "numerado", que es el de estos enunciados.
ESTANDAR: Dict[str, Tuple[str, str, TipoCuenta, Optional[Rubro]]] = {
    "caja": ("101", "Caja", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "banco": ("102", "Banco", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "clientes": ("103", "Clientes", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "letras_cobrar": ("104", "Letras por Cobrar", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "mercaderias": ("105", "Mercaderías", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "igv_credito": ("106", "IGV Crédito Fiscal", TipoCuenta.ACTIVO, Rubro.CORRIENTE),
    "proveedores": ("201", "Proveedores", TipoCuenta.PASIVO, Rubro.CORRIENTE),
    "letras_pagar": ("202", "Letras por Pagar", TipoCuenta.PASIVO, Rubro.CORRIENTE),
    "igv_debito": ("203", "IGV Débito Fiscal", TipoCuenta.PASIVO, Rubro.CORRIENTE),
    "capital": ("301", "Capital", TipoCuenta.PATRIMONIO, None),
    "ventas": ("401", "Ventas", TipoCuenta.INGRESO, Rubro.VENTAS),
    "arriendo": ("501", "Gastos de Arriendo", TipoCuenta.GASTO, Rubro.GASTO_ADMINISTRACION),
    "costo_ventas": ("502", "Costo de Ventas", TipoCuenta.GASTO, Rubro.COSTO_VENTAS),
    "personal": ("503", "Gastos de Personal", TipoCuenta.GASTO, Rubro.GASTO_ADMINISTRACION),
    "servicios": ("504", "Gastos de Servicios", TipoCuenta.GASTO, Rubro.GASTO_ADMINISTRACION),
}

#: Qué cuenta de gasto usar según cómo el enunciado nombre el desembolso.
GASTOS = (
    ("personal", ("sueldos", "remuneraciones", "planilla", "personal", "salarios")),
    ("servicios", ("servicios", "luz", "agua", "telefono", "internet", "energia")),
    ("arriendo", ("arriendo", "alquiler")),
)

#: Para el asiento de apertura: cómo se nombra cada partida en el enunciado.
PARTIDAS_APERTURA: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("caja", ("efectivo", "caja", "dinero")),
    ("banco", ("cuenta corriente", "banco")),
    ("clientes", ("clientes",)),
    ("letras_cobrar", ("letras por cobrar",)),
    ("mercaderias", ("mercader", "existencias")),
    ("proveedores", ("proveedores",)),
    ("letras_pagar", ("letras por pagar",)),
    ("capital", ("capital",)),
)


class Plan:
    """Encuentra, en el plan de cuentas del caso, la cuenta de cada papel.

    Con `crear=True`, la cuenta que no existe no es un fracaso: se propone
    crearla con su tipo y rubro correctos, y queda anotada en `nuevas`. Así el
    estudiante pega el enunciado sin haber armado antes el plan de cuentas.
    """

    def __init__(self, caso: CasoDominio, crear: bool = False):
        self.caso = caso
        self.crear = crear
        self.nuevas: Dict[str, Cuenta] = {}
        self._cache: Dict[str, Optional[Cuenta]] = {}

    def _buscar(self, papel: str) -> Optional[Cuenta]:
        for grupo in PAPELES.get(papel, ()):
            for cuenta in self.caso.cuentas:
                nombre = _plano(cuenta.nombre)
                if all(palabra in nombre for palabra in grupo):
                    # "Ventas" no debe casar con "Costo de ventas".
                    if papel == "ventas" and cuenta.tipo != TipoCuenta.INGRESO:
                        continue
                    if papel != "costo_ventas" and cuenta.tipo == TipoCuenta.GASTO                             and papel in ("ventas",):
                        continue
                    return cuenta
        return None

    def _codigo_libre(self, deseado: str) -> str:
        ocupados = {c.codigo for c in self.caso.cuentas} | {
            c.codigo for c in self.nuevas.values()
        }
        if deseado not in ocupados:
            return deseado
        for sufijo in range(1, 50):
            tentativa = f"{deseado}-{sufijo}"
            if tentativa not in ocupados:
                return tentativa
        return deseado

    def __call__(self, papel: str) -> Optional[Cuenta]:
        if papel in self._cache:
            return self._cache[papel]
        encontrada = self._buscar(papel)
        if encontrada is None and self.crear and papel in ESTANDAR:
            codigo, nombre, tipo, rubro = ESTANDAR[papel]
            encontrada = Cuenta(
                id="nueva:" + papel,
                codigo=self._codigo_libre(codigo),
                nombre=nombre,
                tipo=tipo,
                rubro=rubro,
            )
            self.nuevas[papel] = encontrada
        self._cache[papel] = encontrada
        return encontrada

    def exige(self, *papeles: str) -> Tuple[List[Cuenta], List[str]]:
        cuentas, faltan = [], []
        for papel in papeles:
            cuenta = self(papel)
            if cuenta is None:
                faltan.append(papel.replace("_", " "))
            else:
                cuentas.append(cuenta)
        return cuentas, faltan


# ------------------------------------------------------------- lo que sale

@dataclass
class LineaPropuesta:
    cuenta: Cuenta
    debe: Decimal = Decimal("0.00")
    haber: Decimal = Decimal("0.00")


@dataclass
class AsientoPropuesto:
    fecha: Optional[date]
    glosa: str
    lineas: List[LineaPropuesta]
    #: Cómo salieron los números, para que el estudiante lo pueda seguir.
    explicacion: List[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((linea.debe for linea in self.lineas), Decimal("0.00"))

    @property
    def cuadra(self) -> bool:
        debe = sum((linea.debe for linea in self.lineas), Decimal("0.00"))
        haber = sum((linea.haber for linea in self.lineas), Decimal("0.00"))
        return debe == haber and debe > 0


@dataclass
class Lectura:
    asientos: List[AsientoPropuesto] = field(default_factory=list)
    #: Operaciones que no se pudieron convertir, con el motivo.
    problemas: List[str] = field(default_factory=list)
    #: Avisos que no impiden el asiento (fechas raras, supuestos tomados).
    avisos: List[str] = field(default_factory=list)
    #: Cuentas que hay que agregar al plan antes de registrar.
    cuentas_nuevas: List[Cuenta] = field(default_factory=list)

    @property
    def hubo_algo(self) -> bool:
        return bool(self.asientos)


# --------------------------------------------------------------- el lector

FECHA = re.compile(r"\b(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{2,4})\b")

#: "al 01 de agosto del 2024": muchos enunciados fechan la apertura así.
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
FECHA_LARGA = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+(?:de[l]?\s+)?(\d{4})\b"
)
PORCENTAJE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
CUENTA_LETRAS = re.compile(r"\b(\d{1,3})\s+(?:de\s+(?:las|los)\s+)?letras\b")
NUMERO_DE_LETRA = re.compile(r"n\s*[.°ºor]*\s*\d+(?:\s*(?:,|y)\s*\d+)*", re.IGNORECASE)
IMPORTE_CON_MONEDA = re.compile(r"s/\.?\s*(\d[\d\s,]*(?:\.\d+)?)", re.IGNORECASE)
IMPORTE_SUELTO = re.compile(r"\b(\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|\d+\.\d{2})\b")

PALABRAS = {
    "apertura": ("inventario inicial", "saldos iniciales", "balance inicial",
                 "presenta el siguiente", "constitucion", "se constituye"),
    "compra": ("compra", "se compran", "adquiere", "adquisicion"),
    "venta": ("venta", "se venden", "se vende", "factura a"),
    "gasto": ("arriendo", "alquiler", "gasto operativo", "se paga el", "servicios",
              "sueldos", "remuneraciones", "publicidad", "luz", "agua"),
    "amortizacion": ("amortizacion", "deuda historica", "deuda que se mantenia",
                     "cancela el", "abona a la deuda"),
    "cobranza": ("cobranza", "cobra", "el cliente cancela", "nos cancela"),
    "pago_letras": ("pago de letras", "paga las letras", "cancela las letras",
                    "letras pendientes"),
    "costo_ventas": ("costo de ventas", "existencia final", "conteo fisico",
                     "diferencia de inventarios", "inventario final"),
}


def _importes(texto: str) -> List[Decimal]:
    """Los montos de la operación, sin confundirlos con números de letra."""
    limpio = NUMERO_DE_LETRA.sub(" ", texto)
    limpio = PORCENTAJE.sub(" ", limpio)
    limpio = CUENTA_LETRAS.sub(" ", limpio)

    valores: List[Decimal] = []
    for crudo in IMPORTE_CON_MONEDA.findall(limpio):
        valores.append(_a_decimal(crudo))
    if valores:
        return valores
    for crudo in IMPORTE_SUELTO.findall(limpio):
        valores.append(_a_decimal(crudo))
    return valores


def _a_decimal(crudo: str) -> Decimal:
    limpio = crudo.replace(" ", "").replace(",", "")
    try:
        return Decimal(limpio)
    except Exception:
        return Decimal("0")


def _fecha(texto: str) -> Optional[date]:
    hallada = FECHA.search(texto)
    if not hallada:
        larga = FECHA_LARGA.search(_plano(texto))
        if not larga:
            return None
        try:
            return date(int(larga.group(3)), MESES[larga.group(2)], int(larga.group(1)))
        except ValueError:
            return None
    dia, mes, anio = (int(parte) for parte in hallada.groups())
    if anio < 100:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _partir(texto: str) -> List[str]:
    """Separa el enunciado en operaciones: una por línea con fecha o viñeta."""
    crudas = [linea.strip(" \t-•*–—") for linea in texto.splitlines()]
    bloques: List[str] = []
    actual: List[str] = []
    for linea in crudas:
        if not linea:
            continue
        empieza = FECHA.match(linea) or _plano(linea).startswith(
            ("la empresa", "al inicio", "el inventario", "se constituye")
        )
        if empieza and actual:
            bloques.append(" ".join(actual))
            actual = [linea]
        else:
            actual.append(linea)
    if actual:
        bloques.append(" ".join(actual))
    return [b for b in bloques if len(b) > 15]


def _clasificar(texto: str) -> Optional[str]:
    """Qué operación es. Se revisa de la marca más inequívoca a la más vaga.

    El puntaje por palabras sueltas no servía: "el cliente cancela el 40%",
    dentro de una venta, pesaba más que "se venden" y la volvía una cobranza.
    """
    plano = _plano(texto)
    hay = lambda *frases: any(frase in plano for frase in frases)

    # Verbos que nombran la operación sin ambigüedad.
    if hay("existencia final", "conteo fisico", "costo de ventas",
           "diferencia de inventarios", "inventario final"):
        return "costo_ventas"
    if hay("se compran", "compra de mercader", "compra mercader", "se adquieren",
           "adquisicion de mercader"):
        return "compra"
    if hay("se venden", "se vende", "venta de mercader", "venta al credito",
           "venta al contado", "factura a"):
        return "venta"

    if "letra" in plano:
        if hay("a favor del proveedor", "letras pendientes", "pago de letras") or (
            "proveedor" in plano and hay("paga", "cancela")
        ):
            return "pago_letras"
        if hay("cliente", "cobranza", "cobra"):
            return "cobranza"

    # "La deuda histórica que mantenían los clientes" es una cobranza, no un
    # pago: lo que decide es de quién es la deuda, no la palabra "deuda".
    cobro = hay("cobranza", "se cobra", "cobra con", "cobra a", "nos cancela",
                "el cliente cancela", "los clientes cancelan")
    if cobro and "proveedor" not in plano:
        return "cobranza"
    if hay("amortizacion", "deuda historica", "deuda que se mantenia",
           "abona a la deuda", "amortiza"):
        return "amortizacion"
    if cobro:
        return "cobranza"
    if hay("arriendo", "alquiler", "gasto operativo", "sueldos", "remuneraciones",
           "publicidad", "servicios basicos", "se paga el"):
        return "gasto"

    # La apertura lista varias partidas con su importe; si hay menos de tres,
    # casi seguro es otra cosa que menciona el inventario inicial de pasada.
    if hay("inventario inicial", "saldos iniciales", "balance inicial",
           "presenta el siguiente", "se constituye", "constitucion"):
        if len(_importes(texto)) >= 3:
            return "apertura"
    if hay("proveedores") and hay("paga", "cancela"):
        return "amortizacion"
    return None


# ------------------------------------------------------------- constructores


@dataclass
class Memoria:
    """Lo que una operación necesita saber de las anteriores."""
    saldo_proveedores: Decimal = Decimal("0.00")
    saldo_clientes: Decimal = Decimal("0.00")
    mercaderias: Decimal = Decimal("0.00")
    valor_letra_pagar: Decimal = Decimal("0.00")
    valor_letra_cobrar: Decimal = Decimal("0.00")


def _separar_igv(texto: str, monto: Decimal) -> Tuple[Decimal, Decimal, str]:
    """Devuelve (base, igv, explicación) según cómo lo diga el enunciado."""
    plano = _plano(texto)
    if "igv incluido" in plano or "incluye igv" in plano or "incluido el igv" in plano:
        base = _r(monto / UNO_MAS_IGV)
        return base, _r(monto - base), (
            f"El total {_n(monto)} incluye IGV: base = {_n(monto)} / 1.18 = {_n(base)}, "
            f"IGV = {_n(monto - base)}."
        )
    if "mas igv" in plano or "mas el igv" in plano or "sin igv" in plano or "neto" in plano:
        igv = _r(monto * IGV)
        return monto, igv, (
            f"{_n(monto)} es el valor de venta: IGV = {_n(monto)} x 0.18 = {_n(igv)}, "
            f"total = {_n(monto + igv)}."
        )
    return monto, Decimal("0.00"), "El enunciado no menciona IGV, así que no se aplicó."


def _forma_de_pago(texto: str, plan: Plan) -> Tuple[Optional[Cuenta], str]:
    plano = _plano(texto)
    if "letra" in plano:
        return plan("letras_pagar"), "letras"
    if "cheque" in plano or "cuenta corriente" in plano or "banco" in plano:
        return plan("banco"), "cheque"
    if "efectivo" in plano or "contado" in plano or "caja" in plano:
        return plan("caja"), "efectivo"
    return plan("proveedores"), "crédito"


def _apertura(texto: str, plan: Plan, memoria: Memoria):
    cuerpo = texto.split(":", 1)[-1]
    # Una coma separa partidas solo si no está entre dígitos (2,500,000).
    piezas = re.split(r",(?!\d)| y ", cuerpo)
    lineas: List[LineaPropuesta] = []
    detalle: List[str] = []
    for pieza in piezas:
        importes = _importes(pieza)
        if not importes:
            continue
        monto = importes[0]
        plano = _plano(pieza)
        for papel, claves in PARTIDAS_APERTURA:
            if any(clave in plano for clave in claves):
                cuenta = plan(papel)
                if cuenta is None:
                    break
                if cuenta.tipo == TipoCuenta.ACTIVO:
                    lineas.append(LineaPropuesta(cuenta, debe=monto))
                else:
                    lineas.append(LineaPropuesta(cuenta, haber=monto))
                if papel == "proveedores":
                    memoria.saldo_proveedores = monto
                elif papel == "clientes":
                    memoria.saldo_clientes = monto
                elif papel == "mercaderias":
                    memoria.mercaderias = monto
                detalle.append(f"{cuenta.nombre}: {_n(monto)}")
                break
    if not lineas:
        return None, "no se reconoció ninguna partida del inventario inicial"
    return AsientoPropuesto(
        fecha=_fecha(texto),
        glosa="Inventario inicial",
        lineas=lineas,
        explicacion=["Cada partida va al Debe si es activo y al Haber si es pasivo "
                     "o patrimonio: " + "; ".join(detalle) + "."],
    ), None


def _compra(texto: str, plan: Plan, memoria: Memoria):
    importes = _importes(texto)
    if not importes:
        return None, "no se encontró el importe de la compra"
    total = max(importes)
    base, igv, explico = _separar_igv(texto, total)
    con_igv = _r(base + igv)

    cuentas, faltan = plan.exige("mercaderias")
    if faltan:
        return None, "falta la cuenta de " + ", ".join(faltan)
    mercaderias = cuentas[0]
    contra, forma = _forma_de_pago(texto, plan)
    if contra is None:
        return None, "falta la cuenta donde registrar el pago (" + forma + ")"

    lineas = [LineaPropuesta(mercaderias, debe=base)]
    if igv > 0:
        cuenta_igv = plan("igv_credito")
        if cuenta_igv is None:
            return None, "falta la cuenta de IGV crédito fiscal"
        lineas.append(LineaPropuesta(cuenta_igv, debe=igv))
    lineas.append(LineaPropuesta(contra, haber=con_igv))

    explicacion = [explico, f"La compra se paga con {forma}."]
    cuantas = CUENTA_LETRAS.search(_plano(texto))
    if forma == "letras" and cuantas:
        numero = int(cuantas.group(1))
        memoria.valor_letra_pagar = _r(con_igv / numero)
        explicacion.append(
            f"Son {numero} letras de igual valor: {_n(con_igv)} / {numero} = "
            f"{_n(memoria.valor_letra_pagar)} cada una."
        )
    memoria.mercaderias += base
    return AsientoPropuesto(_fecha(texto), "Compra de mercaderías", lineas, explicacion), None


def _venta(texto: str, plan: Plan, memoria: Memoria):
    importes = _importes(texto)
    if not importes:
        return None, "no se encontró el importe de la venta"
    monto = max(importes)
    base, igv, explico = _separar_igv(texto, monto)
    total = _r(base + igv)

    cuenta_ventas = plan("ventas")
    if cuenta_ventas is None:
        return None, "falta la cuenta de ventas"

    lineas_haber = [LineaPropuesta(cuenta_ventas, haber=base)]
    if igv > 0:
        cuenta_igv = plan("igv_debito")
        if cuenta_igv is None:
            return None, "falta la cuenta de IGV débito fiscal"
        lineas_haber.append(LineaPropuesta(cuenta_igv, haber=igv))

    explicacion = [explico]
    plano = _plano(texto)
    porcentaje = PORCENTAJE.search(plano)
    lineas_debe: List[LineaPropuesta] = []

    if porcentaje and "letra" in plano:
        parte = Decimal(porcentaje.group(1).replace(",", ".")) / Decimal("100")
        contado = _r(total * parte)
        saldo = _r(total - contado)
        cobro = plan("caja") if ("efectivo" in plano or "contado" in plano) else plan("banco")
        letras = plan("letras_cobrar")
        if cobro is None or letras is None:
            return None, "faltan las cuentas de caja/banco o letras por cobrar"
        lineas_debe = [LineaPropuesta(cobro, debe=contado), LineaPropuesta(letras, debe=saldo)]
        explicacion.append(
            f"Cobra el {porcentaje.group(1)}% del total facturado: {_n(total)} x "
            f"{porcentaje.group(1)}% = {_n(contado)}; el saldo {_n(saldo)} queda en letras."
        )
        cuantas = CUENTA_LETRAS.search(plano)
        if cuantas:
            numero = int(cuantas.group(1))
            memoria.valor_letra_cobrar = _r(saldo / numero)
            explicacion.append(
                f"Son {numero} letras: {_n(saldo)} / {numero} = "
                f"{_n(memoria.valor_letra_cobrar)} cada una."
            )
    else:
        destino, forma = ("caja", "al contado") if (
            "efectivo" in plano or "contado" in plano
        ) else ("clientes", "al crédito")
        cuenta = plan(destino)
        if cuenta is None:
            return None, "falta la cuenta de " + destino
        lineas_debe = [LineaPropuesta(cuenta, debe=total)]
        explicacion.append(f"La venta es {forma}.")
        if destino == "clientes":
            memoria.saldo_clientes += total

    return AsientoPropuesto(
        _fecha(texto), "Venta de mercaderías", lineas_debe + lineas_haber, explicacion
    ), None


def _gasto(texto: str, plan: Plan, memoria: Memoria):
    importes = _importes(texto)
    if not importes:
        return None, "no se encontró el importe del gasto"
    monto = max(importes)
    plano = _plano(texto)
    base, igv, explico = (monto, Decimal("0.00"), "")
    if "mas igv" in plano or "mas el igv" in plano:
        base, igv, explico = _separar_igv(texto, monto)

    papel = "arriendo"
    for candidato, claves in GASTOS:
        if any(clave in plano for clave in claves):
            papel = candidato
            break
    cuenta_gasto = plan(papel)
    if cuenta_gasto is None:
        return None, "falta la cuenta del gasto (arriendo, personal o servicios)"
    contra, forma = _forma_de_pago(texto, plan)
    if contra is None:
        return None, "falta la cuenta con la que se paga"

    lineas = [LineaPropuesta(cuenta_gasto, debe=base)]
    if igv > 0:
        cuenta_igv = plan("igv_credito")
        if cuenta_igv is None:
            return None, "falta la cuenta de IGV crédito fiscal"
        lineas.append(LineaPropuesta(cuenta_igv, debe=igv))
    lineas.append(LineaPropuesta(contra, haber=_r(base + igv)))

    explicacion = [e for e in (explico,) if e]
    explicacion.append(f"Se paga con {forma}.")
    return AsientoPropuesto(_fecha(texto), "Pago de " + cuenta_gasto.nombre.lower(),
                            lineas, explicacion), None


def _amortizacion(texto: str, plan: Plan, memoria: Memoria):
    plano = _plano(texto)
    cuenta_deuda = plan("proveedores")
    contra, forma = _forma_de_pago(texto, plan)
    if cuenta_deuda is None or contra is None:
        return None, "faltan las cuentas de proveedores o de pago"

    porcentaje = PORCENTAJE.search(plano)
    explicacion: List[str] = []
    if porcentaje:
        parte = Decimal(porcentaje.group(1).replace(",", ".")) / Decimal("100")
        if memoria.saldo_proveedores <= 0:
            return None, (
                "dice un porcentaje de la deuda, pero antes no se leyó el saldo "
                "inicial de proveedores"
            )
        monto = _r(memoria.saldo_proveedores * parte)
        explicacion.append(
            f"El {porcentaje.group(1)}% de la deuda inicial con proveedores: "
            f"{_n(memoria.saldo_proveedores)} x {porcentaje.group(1)}% = {_n(monto)}."
        )
        memoria.saldo_proveedores = _r(memoria.saldo_proveedores - monto)
    else:
        importes = _importes(texto)
        if not importes:
            return None, "no se encontró el importe a pagar"
        monto = max(importes)

    explicacion.append(f"Se paga con {forma}.")
    return AsientoPropuesto(
        _fecha(texto),
        "Pago a proveedores",
        [LineaPropuesta(cuenta_deuda, debe=monto), LineaPropuesta(contra, haber=monto)],
        explicacion,
    ), None


def _cobranza(texto: str, plan: Plan, memoria: Memoria):
    plano = _plano(texto)
    destino = plan("banco") if ("cheque" in plano or "banco" in plano) else plan("caja")
    if destino is None:
        return None, "falta la cuenta de caja o banco"

    if "letra" in plano:
        origen = plan("letras_cobrar")
        if origen is None:
            return None, "falta la cuenta de letras por cobrar"
        cuantas = len(re.findall(r"\d+", NUMERO_DE_LETRA.search(plano).group(0))) if (
            NUMERO_DE_LETRA.search(plano)
        ) else 0
        cuenta_texto = CUENTA_LETRAS.search(plano)
        if cuenta_texto:
            cuantas = int(cuenta_texto.group(1))
        if cuantas and memoria.valor_letra_cobrar > 0:
            monto = _r(memoria.valor_letra_cobrar * cuantas)
            explicacion = [
                f"Son {cuantas} letras de {_n(memoria.valor_letra_cobrar)}: "
                f"{_n(monto)} en total."
            ]
        else:
            importes = _importes(texto)
            if not importes:
                return None, (
                    "no se pudo saber cuánto valen esas letras: no se leyó antes la "
                    "venta que las originó"
                )
            monto = max(importes)
            explicacion = []
        return AsientoPropuesto(
            _fecha(texto),
            "Cobro de letras",
            [LineaPropuesta(destino, debe=monto), LineaPropuesta(origen, haber=monto)],
            explicacion,
        ), None

    origen = plan("clientes")
    importes = _importes(texto)
    if origen is None or not importes:
        return None, "falta la cuenta de clientes o el importe"
    monto = max(importes)
    return AsientoPropuesto(
        _fecha(texto),
        "Cobranza a clientes",
        [LineaPropuesta(destino, debe=monto), LineaPropuesta(origen, haber=monto)],
        [],
    ), None


def _pago_letras(texto: str, plan: Plan, memoria: Memoria):
    plano = _plano(texto)
    origen = plan("letras_pagar")
    contra, forma = _forma_de_pago(texto, plan)
    # "cancela con cheque 3 letras": el pago es con cheque, no con más letras.
    if "cheque" in plano or "banco" in plano:
        contra, forma = plan("banco"), "cheque"
    if origen is None or contra is None:
        return None, "faltan las cuentas de letras por pagar o de banco"

    cuantas = CUENTA_LETRAS.search(plano)
    explicacion: List[str] = []
    if cuantas and memoria.valor_letra_pagar > 0:
        numero = int(cuantas.group(1))
        monto = _r(memoria.valor_letra_pagar * numero)
        explicacion.append(
            f"Son {numero} letras de {_n(memoria.valor_letra_pagar)}: {_n(monto)} en total."
        )
    else:
        importes = _importes(texto)
        if not importes:
            return None, (
                "no se pudo saber cuánto valen esas letras: no se leyó antes la "
                "compra que las originó"
            )
        monto = max(importes)
    explicacion.append(f"Se paga con {forma}.")
    return AsientoPropuesto(
        _fecha(texto),
        "Pago de letras a proveedores",
        [LineaPropuesta(origen, debe=monto), LineaPropuesta(contra, haber=monto)],
        explicacion,
    ), None


def _costo_ventas(texto: str, plan: Plan, memoria: Memoria):
    importes = _importes(texto)
    if not importes:
        return None, "no se encontró el valor de la existencia final"
    final = max(importes)
    cuenta_costo = plan("costo_ventas")
    cuenta_merc = plan("mercaderias")
    if cuenta_costo is None or cuenta_merc is None:
        return None, "faltan las cuentas de costo de ventas o mercaderías"
    if memoria.mercaderias <= 0:
        return None, (
            "para el costo de ventas hace falta saber cuánta mercadería entró; "
            "no se leyó antes ninguna compra ni inventario inicial"
        )
    costo = _r(memoria.mercaderias - final)
    if costo <= 0:
        return None, (
            f"la existencia final ({_n(final)}) es mayor que la mercadería que entró "
            f"({_n(memoria.mercaderias)}): revisa el dato"
        )
    explicacion = [
        f"Costo de ventas = mercadería que entró - existencia final = "
        f"{_n(memoria.mercaderias)} - {_n(final)} = {_n(costo)}.",
        f"Después de este asiento, la cuenta {cuenta_merc.nombre} queda en {_n(final)}.",
    ]
    memoria.mercaderias = final
    return AsientoPropuesto(
        _fecha(texto),
        "Costo de ventas por diferencia de inventarios",
        [LineaPropuesta(cuenta_costo, debe=costo), LineaPropuesta(cuenta_merc, haber=costo)],
        explicacion,
    ), None


CONSTRUCTORES = {
    "apertura": _apertura,
    "compra": _compra,
    "venta": _venta,
    "gasto": _gasto,
    "amortizacion": _amortizacion,
    "cobranza": _cobranza,
    "pago_letras": _pago_letras,
    "costo_ventas": _costo_ventas,
}


def leer(texto: str, caso: CasoDominio, crear_cuentas: bool = True) -> Lectura:
    """Convierte el enunciado en asientos propuestos."""
    lectura = Lectura()
    plan = Plan(caso, crear=crear_cuentas)
    memoria = Memoria()

    for numero, bloque in enumerate(_partir(texto), start=1):
        tipo = _clasificar(bloque)
        resumen = bloque[:70] + ("…" if len(bloque) > 70 else "")
        if tipo is None:
            lectura.problemas.append(f"Operación {numero} ({resumen}): no la reconocí.")
            continue
        asiento, motivo = CONSTRUCTORES[tipo](bloque, plan, memoria)
        if asiento is None:
            lectura.problemas.append(f"Operación {numero} ({resumen}): {motivo}.")
            continue
        if not asiento.cuadra:
            lectura.problemas.append(
                f"Operación {numero} ({resumen}): el asiento me salió descuadrado, "
                "así que no te lo propongo."
            )
            continue
        lectura.asientos.append(asiento)

    # Solo las cuentas que de verdad usó algún asiento propuesto.
    usadas = {l.cuenta.codigo for a in lectura.asientos for l in a.lineas}
    lectura.cuentas_nuevas = [c for c in plan.nuevas.values() if c.codigo in usadas]

    anios = {a.fecha.year for a in lectura.asientos if a.fecha}
    if len(anios) > 1:
        lectura.avisos.append(
            "Las fechas del enunciado van de " + str(min(anios)) + " a " + str(max(anios))
            + ". Suele ser un error de tipeo: revísalas antes de registrarlas."
        )
    sin_fecha = [a for a in lectura.asientos if a.fecha is None]
    if sin_fecha:
        lectura.avisos.append(
            f"{len(sin_fecha)} operación(es) no traían fecha; les puse la del período "
            "del caso al registrarlas."
        )
    return lectura


# ------------------------------------------------------------- presentación


def a_markdown(lectura: Lectura, caso: CasoDominio) -> str:
    simbolo = caso.empresa.simbolo_moneda
    partes: List[str] = []

    if lectura.asientos:
        partes.append(
            f"Leí **{len(lectura.asientos)} operación(es)** y así quedan los asientos:"
        )
        for numero, asiento in enumerate(lectura.asientos, start=1):
            fecha = f"{asiento.fecha:%d/%m/%Y}" if asiento.fecha else "sin fecha"
            partes.append(f"\n### {numero}. {asiento.glosa} — {fecha}")
            partes.append("| Código | Cuenta | Debe | Haber |")
            partes.append("| --- | --- | ---: | ---: |")
            for linea in asiento.lineas:
                partes.append(
                    f"| {linea.cuenta.codigo} | {linea.cuenta.nombre} "
                    f"| {_n(linea.debe) if linea.debe else ''} "
                    f"| {_n(linea.haber) if linea.haber else ''} |"
                )
            partes.append(f"| | **Totales** | **{_n(asiento.total)}** | **{_n(asiento.total)}** |")
            for nota in asiento.explicacion:
                if nota:
                    partes.append(f"\n{nota}")

        total = sum((a.total for a in lectura.asientos), Decimal("0.00"))
        partes.append(
            f"\nTodos cuadran. Suma del Debe: **{simbolo} {_n(total)}**."
        )

    if lectura.problemas:
        partes.append("\n### Lo que no pude resolver")
        for problema in lectura.problemas:
            partes.append(f"- {problema}")
        partes.append(
            "\nEsas las tienes que registrar a mano en **Registrar Asiento**. "
            "Si me dices qué cuentas mueve cada una, te digo de qué lado va."
        )

    if lectura.avisos:
        partes.append("")
        for aviso in lectura.avisos:
            partes.append(f"- {aviso}")

    if not lectura.asientos and not lectura.problemas:
        return (
            "No reconocí ninguna operación en ese texto. Pégame el enunciado con una "
            "operación por línea, empezando por la fecha, por ejemplo:\n\n"
            "`01/06/2024 - Se compran mercaderías por S/ 1,000,000 (IGV incluido), "
            "firmando 10 letras.`"
        )
    return "\n".join(partes)


def a_importables(lectura: Lectura, caso: CasoDominio) -> List[dict]:
    """La forma que espera importar_asientos() en servicios/casos.py."""
    respaldo = caso.empresa.periodo_inicio or date.today()
    salida = []
    for numero, asiento in enumerate(lectura.asientos, start=1):
        salida.append({
            "numero": numero,
            "fecha": asiento.fecha or respaldo,
            "glosa": asiento.glosa,
            "lineas": [
                {"codigo": linea.cuenta.codigo, "debe": linea.debe, "haber": linea.haber}
                for linea in asiento.lineas
            ],
        })
    return salida


def parece_enunciado(texto: str) -> bool:
    """¿Vale la pena intentar leerlo como un caso?"""
    if len(texto) < 90:
        return False
    plano = _plano(texto)
    operaciones = sum(1 for palabras in PALABRAS.values() for p in palabras if p in plano)
    fechas = len(FECHA.findall(texto))
    importes = len(IMPORTE_CON_MONEDA.findall(texto)) + len(IMPORTE_SUELTO.findall(texto))
    return importes >= 2 and (fechas >= 1 or operaciones >= 2)


# ------------------------------------------------- crear el caso de la nada

EMPRESA = re.compile(
    r"(?:la\s+empresa\s+|empresa\s*:\s*)([A-ZÁÉÍÓÚÑ][^.,;:\n]{2,70}?"
    r"(?:S\.?A\.?C?\.?|E\.?I\.?R\.?L\.?|S\.?R\.?L\.?))",
    re.IGNORECASE,
)


def datos_del_caso(texto: str) -> dict:
    """Saca del enunciado lo necesario para crear el caso: nombre y período."""
    nombre = "Caso del enunciado"
    hallada = EMPRESA.search(texto)
    if hallada:
        nombre = " ".join(hallada.group(1).split())[:80]

    fechas = []
    for dia, mes, anio in FECHA.findall(texto):
        anio = int(anio)
        if anio < 100:
            anio += 2000
        try:
            fechas.append(date(anio, int(mes), int(dia)))
        except ValueError:
            continue
    for dia, mes, anio in FECHA_LARGA.findall(_plano(texto)):
        try:
            fechas.append(date(int(anio), MESES[mes], int(dia)))
        except ValueError:
            continue
    # Si el enunciado mezcla años (suele ser un tipeo), se usa el más repetido.
    if fechas:
        comun = max({f.year for f in fechas}, key=lambda a: sum(1 for f in fechas if f.year == a))
        delmes = [f for f in fechas if f.year == comun]
        inicio, fin = min(delmes), max(delmes)
    else:
        inicio = fin = None
    return {"nombre": nombre, "razon_social": nombre, "periodo_inicio": inicio, "periodo_fin": fin}


#: Un caso sin nada, para leer un enunciado cuando el usuario no tiene ninguno
#: abierto: todas las cuentas salen como nuevas.
CASO_VACIO = CasoDominio(id="", nombre="", empresa=Empresa(nombre=""))


def resolver(texto: str, caso: Optional[CasoDominio]) -> str:
    """La respuesta del asistente ante un enunciado pegado en el chat."""
    sin_caso = caso is None
    base = caso or CASO_VACIO
    lectura = leer(texto, base)
    cuerpo = a_markdown(lectura, base)
    if not lectura.asientos:
        return cuerpo

    encabezado = []
    if sin_caso:
        datos = datos_del_caso(texto)
        encabezado.append(
            f"No tenías ningún caso abierto, así que preparé uno nuevo: "
            f"**{datos['nombre']}**, con su plan de cuentas. Lo creo al registrar."
        )
    elif lectura.cuentas_nuevas:
        nombres = ", ".join(f"**{c.codigo} {c.nombre}**" for c in lectura.cuentas_nuevas)
        encabezado.append(
            f"A tu plan de cuentas le faltan {len(lectura.cuentas_nuevas)} cuenta(s) para "
            f"este caso: {nombres}. Las agrego al registrar."
        )
    if encabezado:
        return "\n\n".join(encabezado) + "\n\n" + cuerpo
    return cuerpo
