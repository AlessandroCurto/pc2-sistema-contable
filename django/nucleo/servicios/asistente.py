"""El asistente que responde sin salir del servidor: no cuesta nada y no falla.

Tres clases de respuesta:

1. Fichas escritas a mano sobre el uso del sistema y la teoría contable.
2. Revisiones en vivo del caso abierto (si cuadra, qué asiento falla, cuánto es
   la utilidad). Aquí el asistente le gana a cualquier modelo de lenguaje: no
   estima, lee el caso y usa el mismo motor contable que las pantallas.
3. Cuentas pedidas en la pregunta ("cuánto es el IGV de 1,000,000 incluido"),
   que se resuelven con el número que vino en el texto.

Si nada encaja, lo dice y ofrece los temas más cercanos. Nunca inventa.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, List, Optional

from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.balance_general import construir_balance_general
from ..dominio.estado_resultados import construir_estado_resultados
from ..dominio.tipos import Caso as CasoDominio
from . import enunciados

IGV = Decimal("0.18")
CENTIMO = Decimal("0.01")


# --------------------------------------------------------------- utilidades


def normalizar(texto: str) -> str:
    """Sin tildes, en minúsculas y sin signos: 'cómo' y 'como' son lo mismo."""
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ\s./,]", " ", plano)


def _n(valor: Decimal) -> str:
    return f"{valor:,.2f}"


def _numeros(texto: str) -> List[Decimal]:
    """Saca los importes de la pregunta: 1,000,000.00 o 1000000 o 400 mil."""
    encontrados = []
    for crudo in re.findall(r"\d[\d,.]*", texto.replace(" ", "")):
        limpio = crudo.rstrip(".,")
        # 1,000,000.00 -> la coma separa miles; 1.000.000,00 no se usa en Perú.
        limpio = limpio.replace(",", "")
        try:
            valor = Decimal(limpio)
        except Exception:
            continue
        if valor > 0:
            encontrados.append(valor)
    return encontrados


# ------------------------------------------------------------------- fichas


@dataclass
class Ficha:
    clave: str
    titulo: str
    #: Frases que, si aparecen en la pregunta, la mandan directo a esta ficha.
    frases: List[str] = field(default_factory=list)
    #: Palabras sueltas que suman puntos.
    palabras: List[str] = field(default_factory=list)
    texto: str = ""
    #: Si está, la respuesta se arma con el caso abierto.
    vivo: Optional[Callable[[Optional[CasoDominio]], str]] = None


SIN_CASO = (
    "No tienes ningún caso abierto. Ve a **Casos**, crea uno o carga un ejemplo, "
    "y vuelve a preguntarme."
)


# ---- revisiones en vivo del caso -------------------------------------------


def _resumen(caso: Optional[CasoDominio]) -> str:
    if caso is None:
        return SIN_CASO
    simbolo = caso.empresa.simbolo_moneda
    balance = construir_balance_comprobacion(caso)
    estado = construir_estado_resultados(caso)
    general = construir_balance_general(caso)

    partes = [
        f"## {caso.empresa.nombre}",
        f"- Cuentas en el plan: **{len(caso.cuentas)}**",
        f"- Asientos registrados: **{len(caso.asientos)}**",
        f"- Total del Debe: **{simbolo} {_n(balance.total_debe)}**",
        "",
        "### Resultados",
        f"- Ventas netas: {simbolo} {_n(estado.ventas_netas)}",
        f"- Costo de ventas: {simbolo} {_n(estado.costo_ventas)}",
        f"- Utilidad bruta: {simbolo} {_n(estado.utilidad_bruta)}",
        f"- Resultado antes de impuesto: {simbolo} {_n(estado.resultado_antes_impuesto)}",
        f"- Impuesto a la renta ({estado.tasa_impuesto}%): {simbolo} {_n(estado.impuesto)}",
        f"- **Utilidad neta: {simbolo} {_n(estado.utilidad_neta)}**",
        "",
        "### Situación financiera",
        f"- Total activo: {simbolo} {_n(general.total_activo)}",
        f"- Total pasivo: {simbolo} {_n(general.total_pasivo)}",
        f"- Total patrimonio: {simbolo} {_n(general.total_patrimonio)}",
        "",
    ]
    if balance.cuadrado and general.cuadrado:
        partes.append("Todo cuadra: el Debe iguala al Haber y el Activo iguala al Pasivo más el Patrimonio.")
    else:
        partes.append("**Hay algo que revisar.** Pregúntame *por qué no cuadra* y te digo dónde.")
    return "\n".join(partes)


def _asientos_descuadrados(caso: CasoDominio):
    malos = []
    for asiento in caso.asientos:
        debe = sum((linea.debe for linea in asiento.lineas), Decimal("0"))
        haber = sum((linea.haber for linea in asiento.lineas), Decimal("0"))
        if debe != haber:
            malos.append((asiento, debe, haber))
    return malos


def _diagnostico(caso: Optional[CasoDominio]) -> str:
    if caso is None:
        return SIN_CASO
    simbolo = caso.empresa.simbolo_moneda
    balance = construir_balance_comprobacion(caso)
    general = construir_balance_general(caso)

    if not caso.asientos:
        return (
            "Tu caso no tiene asientos todavía, así que no hay nada que cuadrar. "
            "Empieza por **Registrar Asiento**, o impórtalos desde Excel."
        )

    if balance.cuadrado and general.cuadrado:
        return "\n".join([
            "Revisé tu caso y **no encontré ningún descuadre**:",
            "",
            f"- Balance de comprobación: Debe {simbolo} {_n(balance.total_debe)} "
            f"= Haber {simbolo} {_n(balance.total_haber)}.",
            f"- Ecuación contable: Activo {simbolo} {_n(general.total_activo)} "
            f"= Pasivo + Patrimonio {simbolo} {_n(general.total_pasivo_patrimonio)}.",
            "",
            "Si una cifra no te coincide con la del profesor, lo más probable es que la "
            "diferencia esté en un importe mal copiado, no en un descuadre. Compara asiento "
            "por asiento en el **Libro Diario**.",
        ])

    partes = ["Encontré esto:", ""]
    malos = _asientos_descuadrados(caso)
    if malos:
        partes.append(
            f"**{len(malos)} asiento(s) no cuadran** por dentro. El sistema no deja guardarlos "
            "así desde el formulario, o sea que vinieron de una importación o de una edición directa:"
        )
        partes.append("")
        partes.append("| Asiento | Glosa | Debe | Haber | Diferencia |")
        partes.append("| --- | --- | ---: | ---: | ---: |")
        for asiento, debe, haber in malos[:10]:
            partes.append(
                f"| {asiento.numero} | {asiento.glosa[:40]} | {_n(debe)} | {_n(haber)} "
                f"| {_n(debe - haber)} |"
            )
        partes.append("")
        partes.append("Corrígelos en el **Libro Diario**: elimina el asiento y vuelve a registrarlo.")
        return "\n".join(partes)

    if not balance.cuadrado:
        partes.append(
            f"El **Balance de Comprobación** no cuadra: Debe {simbolo} {_n(balance.total_debe)} "
            f"contra Haber {simbolo} {_n(balance.total_haber)}."
        )
    if not general.cuadrado:
        partes.append(
            f"El **Balance General** no cuadra por {simbolo} {_n(abs(general.diferencia))}."
        )
        partes.append("")
        partes.append("Causas típicas, en orden de probabilidad:")
        partes.append(
            "1. Una cuenta quedó con el **tipo equivocado** (por ejemplo un pasivo marcado como "
            "activo). Revísalo en **Plan de Cuentas**."
        )
        partes.append(
            "2. Falta el asiento de **costo de ventas**, así que el inventario quedó inflado."
        )
        partes.append(
            "3. La casilla *el impuesto afecta al patrimonio* está destildada en **Configuración**: "
            "entonces el patrimonio lleva la utilidad antes de impuesto y no se registra la deuda "
            "con SUNAT."
        )
    return "\n".join(partes)


def _mi_igv(caso: Optional[CasoDominio]) -> str:
    if caso is None:
        return SIN_CASO
    credito = Decimal("0")
    debito = Decimal("0")
    por_id = {c.id: c for c in caso.cuentas}
    for asiento in caso.asientos:
        for linea in asiento.lineas:
            cuenta = por_id.get(linea.cuenta_id)
            if cuenta is None or "igv" not in normalizar(cuenta.nombre):
                continue
            nombre = normalizar(cuenta.nombre)
            if "credito" in nombre:
                credito += linea.debe - linea.haber
            elif "debito" in nombre:
                debito += linea.haber - linea.debe
    if credito == 0 and debito == 0:
        return (
            "En tu caso no hay movimientos en cuentas de IGV. Si tu enunciado tiene compras o "
            "ventas con IGV, te falta registrarlo: el IGV de compras va a **IGV Crédito Fiscal** "
            "(activo) y el de ventas a **IGV Débito Fiscal** (pasivo)."
        )
    simbolo = caso.empresa.simbolo_moneda
    saldo = credito - debito
    partes = [
        "## IGV de tu caso",
        f"- IGV Crédito Fiscal (compras): **{simbolo} {_n(credito)}**",
        f"- IGV Débito Fiscal (ventas): **{simbolo} {_n(debito)}**",
        "",
    ]
    if saldo > 0:
        partes.append(
            f"Saldo **a favor tuyo: {simbolo} {_n(saldo)}**. Compraste más de lo que vendiste, "
            "así que ese crédito se arrastra al mes siguiente."
        )
    elif saldo < 0:
        partes.append(
            f"Saldo **a pagar a SUNAT: {simbolo} {_n(-saldo)}**. Es la diferencia entre el IGV "
            "que cobraste y el que pagaste."
        )
    else:
        partes.append("El crédito y el débito se anulan: no hay nada por pagar ni por arrastrar.")
    return "\n".join(partes)


#: "¿cuál es mi utilidad neta?" nombra una cifra: hay que dar la suya, no la
#: de un ejemplo. Van de la más específica a la más general, porque "costo de
#: ventas" contiene "ventas" y si no, ganaría la equivocada.
CIFRAS: List[tuple] = [
    ("Costo de ventas", "resultado", ("costo de ventas", "costo de la mercaderia", "costo"),
     lambda e, g, b: e.costo_ventas),
    ("Utilidad antes del impuesto", "resultado",
     ("antes de impuesto", "antes del impuesto", "resultado antes"),
     lambda e, g, b: e.resultado_antes_impuesto),
    ("Utilidad bruta", "resultado", ("utilidad bruta", "ganancia bruta"),
     lambda e, g, b: e.utilidad_bruta),
    ("Utilidad neta", "resultado",
     ("utilidad neta", "ganancia neta", "resultado neto", "cuanto gane", "cuanto gano",
      "cuanto ganamos", "cuanto gane"),
     lambda e, g, b: e.utilidad_neta),
    ("Impuesto a la renta", "resultado", ("impuesto",), lambda e, g, b: e.impuesto),
    ("Ventas netas", "resultado",
     ("ventas", "ingresos", "cuanto vendi", "cuanto vendimos", "cuanto vendio"),
     lambda e, g, b: e.ventas_netas),
    ("Total del activo", "balance", ("activo",), lambda e, g, b: g.total_activo),
    ("Total del pasivo", "balance", ("pasivo",), lambda e, g, b: g.total_pasivo),
    ("Total del patrimonio", "balance", ("patrimonio",), lambda e, g, b: g.total_patrimonio),
    ("Suma del Debe", "balance", ("total del debe", "suma del debe", "total movido"),
     lambda e, g, b: b.total_debe),
    ("Dinero disponible", "efectivo",
     ("dinero", "plata", "efectivo", "liquidez", "caja y banco", "en caja", "en el banco",
      "cuanto tengo", "disponible"),
     lambda e, g, b: _efectivo(g)),
    ("Utilidad neta", "resultado", ("utilidad", "ganancia"), lambda e, g, b: e.utilidad_neta),
]

#: Si la pregunta trae algo de esto, quiere la explicación y no el número.
#: Se busca en cualquier parte: "¿y el impuesto cómo se calcula?" también cuenta.
QUIERE_TEORIA = (
    "que es", "que son", "que significa", "definicion", "concepto", "formula",
    "como se calcula", "como calcula", "como calculas", "como calcular", "como calculo",
    "calcular", "calculo del", "el calculo",
    "como se saca", "como sacas", "como saco", "como obtienes", "como se obtiene",
    "como se halla", "para calcular", "para hallar", "para que sirve", "como funciona",
    "explicame", "explica",
    # Preguntas sobre los parámetros del propio sistema, no sobre el caso.
    "que tasa", "que porcentaje", "que igv", "cual es la tasa", "usas", "aplicas",
    "trabajas", "manejas", "redondeas",
    # Piden el recorrido del dinero, no su saldo.
    "se fue", "se movio", "flujo", "entradas y salidas", "en que se gasto",
    "movimientos", "de donde salio",
    # Un "por qué" pide una explicación, nunca un saldo.
    "por que",
)


def cifra_pedida(pregunta: str) -> Optional[int]:
    """La posición en CIFRAS de lo que está preguntando, si pide una cifra."""
    limpia = normalizar(pregunta).strip()
    # "mi" / "mis" manda: quien dice "mi costo de ventas" quiere su número,
    # aunque la frase traiga un verbo que en otro contexto pediría la teoría.
    suyo = re.search(r"(mi|mis)", limpia) is not None
    if not suyo and any(marca in limpia for marca in QUIERE_TEORIA):
        return None
    for indice, (_, _, palabras, _) in enumerate(CIFRAS):
        if any(palabra in limpia for palabra in palabras):
            return indice
    return None


def _responder_cifra(indice: int, caso: Optional[CasoDominio]) -> str:
    if caso is None:
        return SIN_CASO
    etiqueta, grupo, _, obtener = CIFRAS[indice]
    simbolo = caso.empresa.simbolo_moneda
    estado = construir_estado_resultados(caso)
    general = construir_balance_general(caso)
    balance = construir_balance_comprobacion(caso)

    partes = [
        f"**{etiqueta}** de {caso.empresa.nombre}: "
        f"**{simbolo} {_n(obtener(estado, general, balance))}**",
        "",
    ]

    if grupo == "efectivo":
        partes.append("Es la suma de las cuentas que son dinero de verdad:")
        partes.append("")
        partes.append(f"| Cuenta | {simbolo} |")
        partes.append("| --- | ---: |")
        for detalle in _cuentas_de_dinero(general):
            partes.append(
                f"| {detalle.cuenta.codigo} {detalle.cuenta.nombre} | {_n(detalle.monto)} |"
            )
        partes.append(f"| **Disponible** | **{_n(_efectivo(general))}** |")
        otras = [d for d in general.activo_corriente.cuentas
                 if d not in list(_cuentas_de_dinero(general))]
        if otras:
            nombres = ", ".join(d.cuenta.nombre for d in otras)
            partes += [
                "",
                f"El activo total es {simbolo} {_n(general.total_activo)}, pero el resto "
                f"**todavía no es dinero**: {nombres}. Hay que cobrarlo o venderlo primero.",
            ]
        partes.append("\nSi quieres ver cómo se movió, pregúntame *a dónde se fue la plata*.")
    elif grupo == "resultado":
        partes += [
            "De dónde sale:",
            "",
            f"| Concepto | {simbolo} |",
            "| --- | ---: |",
            f"| Ventas netas | {_n(estado.ventas_netas)} |",
            f"| (-) Costo de ventas | {_n(estado.costo_ventas)} |",
            f"| **Utilidad bruta** | **{_n(estado.utilidad_bruta)}** |",
        ]
        if estado.gasto_administracion:
            partes.append(f"| (-) Gastos de administración | {_n(estado.gasto_administracion)} |")
        if estado.gasto_ventas:
            partes.append(f"| (-) Gastos de ventas | {_n(estado.gasto_ventas)} |")
        partes += [
            f"| **Resultado antes del impuesto** | **{_n(estado.resultado_antes_impuesto)}** |",
            f"| (-) Impuesto a la renta ({estado.tasa_impuesto}%) | {_n(estado.impuesto)} |",
            f"| **Utilidad neta** | **{_n(estado.utilidad_neta)}** |",
            "",
            "Está en **Reportes → Estado de Resultados**.",
        ]
    else:
        partes += [
            "El Balance General de tu caso:",
            "",
            f"| Concepto | {simbolo} |",
            "| --- | ---: |",
            f"| Total activo | {_n(general.total_activo)} |",
            f"| Total pasivo | {_n(general.total_pasivo)} |",
            f"| Total patrimonio | {_n(general.total_patrimonio)} |",
            f"| **Pasivo + Patrimonio** | **{_n(general.total_pasivo_patrimonio)}** |",
            "",
            "Está en **Reportes → Balance General**."
            + ("" if general.cuadrado else " **Ojo: no cuadra.**"),
        ]

    partes.append(
        "\nSi lo que querías era la explicación y no el número, pregúntame "
        "*cómo se calcula* eso mismo."
    )
    return "\n".join(partes)


def _cuentas_de_dinero(general):
    """Las cuentas del balance que son dinero de verdad: caja y banco."""
    for detalle in general.activo_corriente.cuentas:
        nombre = normalizar(detalle.cuenta.nombre)
        if any(p in nombre for p in ("caja", "efectivo", "banco", "cuenta corriente")):
            yield detalle


def _efectivo(general) -> Decimal:
    return sum((d.monto for d in _cuentas_de_dinero(general)), Decimal("0.00"))


def _movimientos_de_dinero(caso: CasoDominio):
    """Entradas y salidas de caja y banco, asiento por asiento."""
    dinero = set()
    for cuenta in caso.cuentas:
        nombre = normalizar(cuenta.nombre)
        if any(p in nombre for p in ("caja", "efectivo", "banco", "cuenta corriente")):
            dinero.add(cuenta.id)
    for asiento in sorted(caso.asientos, key=lambda a: (a.fecha, a.numero)):
        entra = sum((l.debe for l in asiento.lineas if l.cuenta_id in dinero), Decimal("0"))
        sale = sum((l.haber for l in asiento.lineas if l.cuenta_id in dinero), Decimal("0"))
        if entra or sale:
            yield asiento, entra, sale


def _flujo_de_efectivo(caso: Optional[CasoDominio]) -> str:
    """De dónde salió y a dónde se fue la plata. Ganancia no es caja."""
    if caso is None:
        return SIN_CASO
    if not caso.asientos:
        return "El caso no tiene asientos, así que no hay movimientos de dinero."
    simbolo = caso.empresa.simbolo_moneda
    general = construir_balance_general(caso)
    estado = construir_estado_resultados(caso)
    movimientos = list(_movimientos_de_dinero(caso))
    if not movimientos:
        return "En este caso no hay movimientos de caja ni de banco."

    # El primer asiento suele ser la apertura: ese saldo es el punto de partida.
    primero, entra, _ = movimientos[0]
    apertura = entra if len(primero.lineas) > 2 and not any(
        l.haber for l in primero.lineas if l.debe == 0) else Decimal("0")
    inicial = entra if "inicial" in normalizar(primero.glosa) else Decimal("0")

    partes = [
        "## Cómo se movió el dinero",
        "",
        "| Fecha | Operación | Entra | Sale |",
        "| --- | --- | ---: | ---: |",
    ]
    total_entra = total_sale = Decimal("0.00")
    for asiento, entra, sale in movimientos:
        partes.append(
            f"| {asiento.fecha:%d/%m} | {asiento.glosa[:44]} "
            f"| {_n(entra) if entra else ''} | {_n(sale) if sale else ''} |"
        )
        total_entra += entra
        total_sale += sale
    partes.append(f"| | **Totales** | **{_n(total_entra)}** | **{_n(total_sale)}** |")

    final = _efectivo(general)
    variacion = total_entra - total_sale
    partes += [
        "",
        f"Al cierre quedan **{simbolo} {_n(final)}** entre caja y banco.",
    ]
    if inicial:
        neto = variacion - inicial
        signo = "más" if neto >= 0 else "menos"
        partes.append(
            f"\nDescontando el saldo inicial de {simbolo} {_n(inicial)}, en el período entró "
            f"{simbolo} {_n(total_entra - inicial)} y salió {simbolo} {_n(total_sale)}: "
            f"**{simbolo} {_n(abs(neto))} {signo}** que al empezar."
        )
        if estado.utilidad_neta > 0 and neto < 0:
            partes.append(
                f"\nFíjate en esto: la empresa **ganó {simbolo} {_n(estado.utilidad_neta)}** "
                f"y sin embargo tiene menos dinero que antes. **Ganancia y caja no son lo "
                f"mismo**: parte del dinero se fue a comprar mercadería que aún no se vende, "
                f"parte de la venta todavía está por cobrar, y pagar deudas reduce la caja "
                f"sin ser un gasto."
            )
    return "\n".join(partes)


def _por_ciento(parte: Decimal, total: Decimal) -> Optional[Decimal]:
    if total == 0:
        return None
    return (parte / total * 100).quantize(Decimal("0.1"))


def _conclusiones(caso: Optional[CasoDominio]) -> str:
    """Lee el caso y dice qué significan sus cifras, no solo cuáles son."""
    if caso is None:
        return SIN_CASO
    simbolo = caso.empresa.simbolo_moneda
    estado = construir_estado_resultados(caso)
    general = construir_balance_general(caso)
    balance = construir_balance_comprobacion(caso)
    if not caso.asientos:
        return "El caso no tiene asientos todavía, así que no hay nada que concluir."

    partes = [f"## Conclusiones — {caso.empresa.nombre}", ""]

    # --- resultado del período
    bruto = _por_ciento(estado.utilidad_bruta, estado.ventas_netas)
    neto = _por_ciento(estado.utilidad_neta, estado.ventas_netas)
    partes.append("### Resultado del período")
    if estado.ventas_netas == 0:
        partes.append("No hubo ventas en el período, así que no hay margen que medir.")
    elif estado.utilidad_neta > 0:
        partes.append(
            f"La empresa **ganó {simbolo} {_n(estado.utilidad_neta)}** sobre ventas de "
            f"{simbolo} {_n(estado.ventas_netas)}: un **margen neto del {neto}%**. "
            f"De cada 100 soles vendidos le quedaron {neto} después de costos, gastos e "
            f"impuesto."
        )
        partes.append(
            f"\nEl margen bruto fue del **{bruto}%**, o sea que la mercadería se vendió a "
            f"{bruto} por ciento por encima de lo que costó. Entre ese margen y el neto se "
            f"fueron los gastos ({simbolo} {_n(estado.total_gastos - estado.costo_ventas)}) "
            f"y el impuesto a la renta ({simbolo} {_n(estado.impuesto)})."
        )
    else:
        partes.append(
            f"La empresa **perdió {simbolo} {_n(abs(estado.utilidad_neta))}** en el período. "
            f"Las ventas fueron {simbolo} {_n(estado.ventas_netas)} y no alcanzaron a cubrir "
            f"el costo de ventas más los gastos. Por eso no hay impuesto a la renta: solo se "
            f"paga sobre utilidad positiva."
        )

    # --- situación financiera
    partes += ["", "### Situación financiera"]
    corriente = general.activo_corriente.total
    deuda_corta = general.pasivo_corriente.total
    if deuda_corta > 0:
        razon = (corriente / deuda_corta).quantize(Decimal("0.01"))
        if razon >= Decimal("2"):
            juicio = "holgada: puede pagar sus deudas de corto plazo sin apuros"
        elif razon >= Decimal("1"):
            juicio = "ajustada pero suficiente: cubre sus deudas de corto plazo"
        else:
            juicio = "**insuficiente**: sus deudas de corto plazo superan a su activo corriente"
        partes.append(
            f"Por cada sol que debe a corto plazo tiene **{simbolo} {razon}** de activo "
            f"corriente. Es una posición {juicio}."
        )
    endeudamiento = _por_ciento(general.total_pasivo, general.total_activo)
    if endeudamiento is not None:
        propio = (Decimal("100") - endeudamiento).quantize(Decimal("0.1"))
        partes.append(
            f"\nEl **{endeudamiento}% del activo está financiado con deuda** y el {propio}% "
            + ("con capital propio. Es una estructura poco apalancada."
               if endeudamiento < 50 else
               "con capital propio. La empresa depende bastante de terceros.")
        )

    # --- IGV, si lo hay
    credito = next((d.monto for d in general.activo_corriente.cuentas
                    if "credito" in normalizar(d.cuenta.nombre)), Decimal("0"))
    debito = next((d.monto for d in general.pasivo_corriente.cuentas
                   if "debito" in normalizar(d.cuenta.nombre)), Decimal("0"))
    if credito or debito:
        partes += ["", "### IGV"]
        saldo = credito - debito
        if saldo > 0:
            partes.append(
                f"El IGV de las compras ({simbolo} {_n(credito)}) supera al de las ventas "
                f"({simbolo} {_n(debito)}): queda un **crédito de {simbolo} {_n(saldo)} a "
                f"favor**, que se arrastra al mes siguiente. No hay nada que pagar a SUNAT."
            )
        elif saldo < 0:
            partes.append(
                f"El IGV de las ventas ({simbolo} {_n(debito)}) supera al de las compras "
                f"({simbolo} {_n(credito)}): hay **{simbolo} {_n(-saldo)} por pagar a SUNAT**."
            )

    # --- control
    partes += ["", "### Control"]
    if balance.cuadrado and general.cuadrado:
        partes.append(
            f"Los {len(caso.asientos)} asientos cuadran, el Balance de Comprobación cierra en "
            f"{simbolo} {_n(balance.total_debe)} de los dos lados y se cumple la ecuación "
            f"contable. **La información es consistente.**"
        )
    else:
        partes.append("**Hay un descuadre.** Pregúntame *por qué no cuadra* y te digo dónde.")
    return "\n".join(partes)


def _parametros(caso: Optional[CasoDominio]) -> str:
    """Con qué números trabaja la aplicación, y los del caso abierto."""
    partes = [
        "## Las tasas que uso",
        "",
        "| Concepto | Tasa |",
        "| --- | --- |",
        "| IGV | **18%** (Perú). Fija: está en el cálculo, no se configura. |",
        "| Impuesto a la renta | **29.5%** por omisión (tercera categoría), "
        "pero se cambia por caso en **Configuración**. |",
        "",
    ]
    if caso is not None:
        tasa = caso.empresa.tasa_impuesto_renta
        partes += [
            f"En tu caso **{caso.empresa.nombre}** la tasa del impuesto a la renta está "
            f"en **{tasa}%**.",
            "",
        ]
        if tasa == 0:
            partes.append(
                "Con 0% no se calcula impuesto, así que tu utilidad neta sale igual a la "
                "utilidad antes de impuesto. Si eso no es lo que quieres, cámbiala a 29.5 "
                "en **Sistema → Configuración**."
            )
        else:
            partes.append(
                "El impuesto se aplica solo si el resultado es positivo; si hay pérdida, es 0."
            )
        partes.append("")
    partes += [
        "## Cómo hago las cuentas",
        "",
        "- Trabajo con **decimales exactos**, no con los números con coma flotante del "
        "navegador: 0.1 + 0.2 da exactamente 0.30.",
        "- Redondeo a **2 decimales**, al alza desde el 5 (medio hacia arriba).",
        "- Los cinco reportes salen siempre de tus asientos; no guardo totales aparte, "
        "así que no pueden quedar desfasados.",
        "- Un asiento **solo se guarda si el Debe iguala al Haber**.",
    ]
    return "\n".join(partes)


def _mis_asientos(caso: Optional[CasoDominio]) -> str:
    if caso is None:
        return SIN_CASO
    if not caso.asientos:
        return "Tu caso todavía no tiene asientos."
    simbolo = caso.empresa.simbolo_moneda
    partes = [f"Tienes **{len(caso.asientos)} asientos** registrados:", ""]
    partes.append("| N.º | Fecha | Glosa | Importe |")
    partes.append("| --- | --- | --- | ---: |")
    for asiento in sorted(caso.asientos, key=lambda a: (a.fecha, a.numero))[:30]:
        total = sum((linea.debe for linea in asiento.lineas), Decimal("0"))
        partes.append(
            f"| {asiento.numero} | {asiento.fecha:%d/%m/%Y} | {asiento.glosa[:46]} "
            f"| {simbolo} {_n(total)} |"
        )
    partes.append("")
    partes.append("Los ves completos en el **Libro Diario**, con filtro por texto y por cuenta.")
    return "\n".join(partes)


def _calcular_igv(caso, pregunta: str) -> Optional[str]:
    """Si la pregunta trae un monto, hace la cuenta con ese monto."""
    montos = _numeros(pregunta)
    if not montos:
        return None
    monto = max(montos)
    incluido = any(p in pregunta for p in ("incluido", "incluye", "inc igv", "con igv"))
    partes = []
    if incluido:
        base = (monto / (1 + IGV)).quantize(Decimal("0.01"))
        impuesto = monto - base
        partes = [
            f"De **{_n(monto)}** con el IGV ya incluido:",
            "",
            f"- Base imponible: {_n(monto)} / 1.18 = **{_n(base)}**",
            f"- IGV (18%): {_n(monto)} - {_n(base)} = **{_n(impuesto)}**",
            f"- Total: **{_n(monto)}**",
        ]
    else:
        impuesto = (monto * IGV).quantize(Decimal("0.01"))
        partes = [
            f"De **{_n(monto)}** como valor de venta (sin IGV):",
            "",
            f"- Base imponible: **{_n(monto)}**",
            f"- IGV (18%): {_n(monto)} × 0.18 = **{_n(impuesto)}**",
            f"- Total a facturar: **{_n(monto + impuesto)}**",
        ]
        partes.append("")
        partes.append(
            "Si ese monto en realidad *ya incluía* el IGV, dímelo con la palabra "
            "«incluido» y lo recalculo al revés."
        )
    return "\n".join(partes)


# ---- fichas de contenido ----------------------------------------------------

FICHAS: List[Ficha] = [
    # ----------------------------------------------------- en vivo
    Ficha(
        clave="resumen",
        titulo="Cómo está mi caso",
        frases=[
            "como esta mi caso", "resumen de mi caso", "resumen del caso", "mi caso",
            "resuelveme el caso", "resuelve el caso", "como va mi caso", "estado de mi caso",
            "revisa mi caso", "analiza mi caso",
        ],
        palabras=["resumen", "caso", "estado", "revisa", "resuelve"],
        vivo=_resumen,
    ),
    Ficha(
        clave="diagnostico",
        titulo="Por qué no cuadra",
        frases=[
            "no cuadra", "por que no cuadra", "descuadr", "no me cuadra", "esta mal",
            "no coincide", "cuadra mi balance", "revisar errores", "tengo un error",
        ],
        palabras=["cuadra", "cuadrar", "descuadre", "error", "mal", "coincide", "diferencia"],
        vivo=_diagnostico,
    ),
    Ficha(
        clave="mi-igv",
        titulo="El IGV de mi caso",
        frases=["mi igv", "cuanto igv tengo", "igv de mi caso", "igv acumulado", "igv por pagar"],
        palabras=["igv", "mi", "tengo", "acumulado"],
        vivo=_mi_igv,
    ),
    Ficha(
        clave="mis-asientos",
        titulo="Mis asientos",
        frases=["mis asientos", "que asientos tengo", "lista de asientos", "ver mis asientos"],
        palabras=["asientos", "mis", "lista", "tengo"],
        vivo=_mis_asientos,
    ),
    # ----------------------------------------------------- uso del sistema
    Ficha(
        clave="registrar-asiento",
        titulo="Registrar un asiento",
        frases=[
            "como registro un asiento", "registrar asiento", "crear asiento", "nuevo asiento",
            "como hago un asiento", "anotar asiento", "como registro",
        ],
        palabras=["registrar", "asiento", "crear", "nuevo", "anotar", "hacer"],
        texto="""## Registrar un asiento

Ve a **Operaciones → Registrar Asiento**.

1. **Fecha** y **glosa** (la descripción de la operación).
2. Una fila por cuenta. Hay dos formas de llenarla, usa la que prefieras:
   - **Debe / Haber**: escribes el importe en la columna que toca.
   - **Signo y monto**: pones `+` o `-` y el importe; el sistema decide el lado según el
     tipo de cuenta. Un `+` en una cuenta de activo va al Debe; en una de pasivo, al Haber.
3. **Guardar**.

El asiento **solo se guarda si el Debe iguala al Haber**. Si no cuadra, el sistema te
muestra la diferencia y no guarda nada: así nunca te queda un libro inconsistente.

Para borrarlo, entra al **Libro Diario** y usa Eliminar en la fila del asiento.""",
    ),
    Ficha(
        clave="importar-excel",
        titulo="Importar asientos desde Excel",
        frases=[
            "importar excel", "importar asientos", "subir excel", "cargar excel", "importar csv",
            "desde excel", "importar desde excel", "plantilla excel",
        ],
        palabras=["importar", "excel", "csv", "subir", "cargar", "plantilla", "xlsx"],
        texto="""## Importar asientos desde Excel o CSV

En **Registrar Asiento** hay un botón para **descargar la plantilla**. Úsala: ya trae los
nombres de columna correctos.

Las columnas son:

| Columna | Qué lleva |
| --- | --- |
| `numero` | Número del asiento. **Las filas con el mismo número forman un asiento.** |
| `fecha` | `dd/mm/aaaa` o `aaaa-mm-dd` |
| `glosa` | La descripción |
| `codigo` | El código de la cuenta, tal como está en tu Plan de Cuentas |
| `debe` | Importe al Debe (0 si no aplica) |
| `haber` | Importe al Haber (0 si no aplica) |

También acepta nombres parecidos: `Nro` por `numero`, `Cargo` por `debe` y `Abono` por `haber`.

Cada asiento pasa por la misma revisión de Debe = Haber. **Los que cuadran entran y los que
no se informan uno por uno**, con el motivo. No se queda nada a medias.

Si un código no existe en tu plan de cuentas, te lo dice en vez de inventar la cuenta.""",
    ),
    Ficha(
        clave="crear-caso",
        titulo="Crear o abrir un caso",
        frases=[
            "crear un caso", "nuevo caso", "como creo un caso", "abrir caso", "cambiar de caso",
            "caso de ejemplo", "cargar ejemplo",
        ],
        palabras=["caso", "crear", "nuevo", "abrir", "cambiar", "ejemplo"],
        texto="""## Casos

Un **caso** es un enunciado completo: la empresa, su plan de cuentas y sus asientos.

En **Principal → Casos** puedes:

- **Crear uno nuevo**: nombre, razón social, RUC (11 dígitos), moneda, período y tasa del
  impuesto a la renta. Eliges un plan de cuentas de partida: el numerado (101, 201, 301…),
  el PCGE simplificado, o vacío para armarlo tú.
- **Abrir** cualquier caso guardado, para cambiar entre ejercicios.
- **Cargar un caso de ejemplo**: vienen tres resueltos, útiles para ver cómo queda cada
  reporte antes de escribir el tuyo.
- **Exportar a JSON** (respaldo completo) e **importarlo** después. Sirve para pasar tu caso
  de una computadora a otra.""",
    ),
    Ficha(
        clave="plan-cuentas",
        titulo="Plan de cuentas",
        frases=[
            "plan de cuentas", "agregar cuenta", "crear cuenta", "nueva cuenta", "editar cuenta",
            "eliminar cuenta", "borrar cuenta", "no puedo eliminar",
        ],
        palabras=["cuenta", "cuentas", "plan", "agregar", "eliminar", "borrar", "editar"],
        texto="""## Plan de Cuentas

En **Operaciones → Plan de Cuentas** agregas, editas y eliminas cuentas.

Cada cuenta lleva:

- **Código** (no se puede repetir dentro del caso)
- **Nombre**
- **Tipo**: Activo, Pasivo, Patrimonio, Ingreso o Gasto
- **Rubro**: corriente / no corriente, o la clasificación del resultado

El tipo es lo más importante: de él dependen el lado del asiento en el modo de signo y
en qué bloque del Balance General aparece la cuenta. **Si una cuenta tiene el tipo
equivocado, el balance no cuadra.**

**Una cuenta con movimientos no se puede eliminar**, y el sistema te dice por qué. Primero
tendrías que borrar los asientos que la usan.""",
    ),
    Ficha(
        clave="descargas",
        titulo="PDF y Excel",
        frases=[
            "descargar pdf", "generar pdf", "exportar excel", "descargar excel", "imprimir",
            "reporte pdf", "como descargo", "exportar reportes",
        ],
        palabras=["pdf", "excel", "descargar", "exportar", "imprimir", "reporte"],
        texto="""## Descargas

En **Descargas**:

- **Reporte PDF**: eliges qué secciones incluir (Libro Diario, Mayor, Balance de
  Comprobación, Estado de Resultados, Balance General). Sale con portada, los datos de la
  empresa y las páginas numeradas.
- **Excel**: un archivo con **una hoja por reporte**, más el plan de cuentas. Las cifras van
  como números, no como texto, así que puedes seguir trabajando sobre ellas.

Cada pantalla de reporte tiene además su botón **Imprimir**, que oculta el menú y deja solo
el cuadro.""",
    ),
    Ficha(
        clave="configuracion",
        titulo="Configuración",
        frases=[
            "configuracion", "cambiar ruc", "cambiar moneda", "tasa de impuesto", "cambiar nombre",
            "impuesto afecta al patrimonio", "cambiar periodo",
        ],
        palabras=["configuracion", "ruc", "moneda", "tasa", "periodo", "patrimonio", "cambiar"],
        texto="""## Configuración

En **Sistema → Configuración** cambias los datos del caso abierto: razón social, RUC,
símbolo de la moneda, período y **tasa del impuesto a la renta**.

La casilla **«el impuesto afecta al patrimonio»** decide cómo se presenta el resultado en
el Balance General:

- **Marcada (lo correcto)**: el patrimonio muestra la **utilidad neta** y el impuesto
  aparece en el pasivo como *Impuesto a la renta por pagar*. Es lo correcto porque ese
  dinero le pertenece a SUNAT, no a los socios.
- **Sin marcar**: el patrimonio muestra la utilidad **antes** de impuesto y no se registra
  la deuda. Algunos profesores lo piden así para simplificar.""",
    ),
    Ficha(
        clave="reportes",
        titulo="Los reportes",
        frases=[
            "libro diario", "libro mayor", "balance de comprobacion", "estado de resultados",
            "balance general", "donde veo los reportes", "que reportes hay",
        ],
        palabras=["libro", "diario", "mayor", "balance", "comprobacion", "estado", "resultados",
                  "general", "reportes"],
        texto="""## Los cinco reportes

Todos se calculan solos a partir de tus asientos, en **Reportes**:

| Reporte | Para qué sirve |
| --- | --- |
| **Libro Diario** | Todos los asientos en orden de fecha. Tiene filtro por texto y por cuenta. |
| **Libro Mayor** | Los mismos movimientos, pero agrupados por cuenta, con el saldo que va quedando. |
| **Balance de Comprobación** | Sumas y saldos de cada cuenta. Sirve para verificar que Debe = Haber. |
| **Estado de Resultados** | Ventas - costo de ventas - gastos = utilidad. Aplica el impuesto a la renta. |
| **Balance General** | La foto final: Activo = Pasivo + Patrimonio. |

No hay nada que recalcular a mano: si agregas un asiento, los cinco se actualizan.""",
    ),
    # ----------------------------------------------------- teoría
    Ficha(
        clave="partida-doble",
        titulo="Partida doble",
        frases=[
            "partida doble", "que es la partida doble", "por que debe igual haber",
            "principio de partida doble",
        ],
        palabras=["partida", "doble", "principio"],
        texto="""## La partida doble

Toda operación afecta **al menos dos cuentas**, y la suma del Debe siempre iguala a la del
Haber. No es una regla arbitraria: es que todo movimiento tiene origen y destino.

Si compras mercadería por 20,000 en efectivo:

| Código | Cuenta | Debe | Haber |
| --- | --- | ---: | ---: |
| 105 | Mercaderías | 20,000.00 | 0.00 |
| 101 | Caja | 0.00 | 20,000.00 |

Entró mercadería (aumenta un activo, va al Debe) y salió efectivo (disminuye otro activo,
va al Haber). El total movido es el mismo de los dos lados.

De aquí sale la **ecuación contable**: `Activo = Pasivo + Patrimonio`. Si cada asiento
cuadra, la ecuación cuadra siempre.""",
    ),
    Ficha(
        clave="naturaleza",
        titulo="Qué va al Debe y qué al Haber",
        frases=[
            "que va al debe", "que va al haber", "debe o haber", "naturaleza de las cuentas",
            "cuando va al debe", "como se cuando", "deudora o acreedora", "naturaleza",
        ],
        palabras=["debe", "haber", "naturaleza", "deudora", "acreedora", "lado"],
        texto="""## Qué va al Debe y qué al Haber

| Tipo de cuenta | Naturaleza | Aumenta en | Disminuye en |
| --- | --- | --- | --- |
| **Activo** | Deudora | Debe | Haber |
| **Gasto** | Deudora | Debe | Haber |
| **Pasivo** | Acreedora | Haber | Debe |
| **Patrimonio** | Acreedora | Haber | Debe |
| **Ingreso** | Acreedora | Haber | Debe |

La forma corta de recordarlo: **lo que tienes y lo que gastas, al Debe. Lo que debes y lo
que ganas, al Haber.**

Ejemplos:
- Cobras a un cliente → Caja **Debe** (aumenta), Clientes **Haber** (disminuye).
- Pagas a un proveedor → Proveedores **Debe** (disminuye la deuda), Banco **Haber**.
- Haces una venta → Caja o Clientes **Debe**, Ventas **Haber**.""",
    ),
    Ficha(
        clave="igv-teoria",
        titulo="Cómo se calcula el IGV",
        frases=[
            "como se calcula el igv", "calcular igv", "calcular el igv", "que es el igv",
            "igv incluido", "mas igv", "sacar el igv", "igv credito fiscal",
            "igv debito fiscal", "como saco el igv", "calculo del igv", "hallar el igv",
        ],
        palabras=["igv", "calcular", "incluido", "credito", "debito", "fiscal", "18"],
        texto="""## El IGV (18% en Perú)

Hay dos maneras de que te den el dato, y se calculan al revés:

**«Más IGV»** — el monto es la base:
- IGV = base × 0.18
- Total = base × 1.18

Ejemplo: 400,000 más IGV → IGV = 72,000 → total 472,000.

**«IGV incluido»** — el monto ya es el total:
- Base = total / 1.18
- IGV = total - base

Ejemplo: 1,000,000 incluido → base = 847,457.63 → IGV = 152,542.37.

### Las dos cuentas

| Operación | Cuenta | Tipo | Por qué |
| --- | --- | --- | --- |
| **Compras** | IGV Crédito Fiscal | Activo | Es un IGV que pagaste y SUNAT te lo reconoce |
| **Ventas** | IGV Débito Fiscal | Pasivo | Es un IGV que cobraste y le debes a SUNAT |

Al cierre del mes se netean: si el débito supera al crédito, la diferencia se paga.

*Pásame un monto y te hago la cuenta: «cuánto es el IGV de 1,000,000 incluido».*""",
    ),
    Ficha(
        clave="impuesto-renta",
        titulo="Impuesto a la renta",
        frases=[
            "impuesto a la renta", "29.5", "como se calcula el impuesto", "tercera categoria",
            "utilidad neta", "impuesto sobre la utilidad", "calcular el impuesto",
            "calculo del impuesto", "hallar el impuesto",
        ],
        palabras=["impuesto", "renta", "utilidad", "neta", "categoria", "calcular"],
        texto="""## Impuesto a la renta

La tasa de **tercera categoría en Perú es 29.5%** y se aplica sobre el resultado antes de
impuesto, **solo si es positivo**. Si la empresa perdió, no hay impuesto.

Por ejemplo, con una utilidad de 150,024.00 (cifras de muestra, **no son las tuyas**):

```
Resultado antes de impuesto  150,024.00
(-) Impuesto 29.5%           (44,257.08)
Utilidad neta                105,766.92
```

*Para tus propias cifras, pregúntame «¿cuál es mi utilidad neta?».*

### Dónde va en el Balance General

El impuesto **no es patrimonio**: es una deuda con SUNAT. Entonces:

- Al **patrimonio** va la **utilidad neta**.
- Al **pasivo corriente** va el impuesto, como *Impuesto a la renta por pagar*.

Esta aplicación lo hace así cuando la casilla «el impuesto afecta al patrimonio» está
marcada en Configuración, que es lo correcto. Muchos apuntes de clase ponen la utilidad
antes de impuesto en el patrimonio y omiten la deuda: el balance igual «cuadra», pero el
patrimonio queda inflado.""",
    ),
    Ficha(
        clave="costo-ventas",
        titulo="Costo de ventas",
        frases=[
            "costo de ventas", "diferencia de inventarios", "como calculo el costo",
            "existencia final", "inventario final", "asiento de costo de ventas",
            "calcular el costo", "calculo del costo", "hallar el costo",
        ],
        palabras=["costo", "ventas", "inventario", "inventarios", "existencia", "diferencia",
                  "calcular"],
        texto="""## Costo de ventas por diferencia de inventarios

La fórmula:

```
Costo de ventas = inventario inicial + compras - inventario final
```

El enunciado casi siempre te da el **inventario final** («el conteo físico determina una
existencia final de S/ 690,360») y tú despejas el costo.

Ejemplo: no había inventario inicial, compraste 847,457.63 y al cierre quedan 690,360:

```
0 + 847,457.63 - 690,360.00 = 157,097.63
```

El asiento:

| Código | Cuenta | Debe | Haber |
| --- | --- | ---: | ---: |
| 502 | Costo de Ventas | 157,097.63 | 0.00 |
| 105 | Mercaderías | 0.00 | 157,097.63 |

Sale mercadería (se consumió) y nace un gasto. Después del asiento, la cuenta Mercaderías
queda justo en el inventario final.""",
    ),
    Ficha(
        clave="ciclo",
        titulo="El ciclo contable",
        frases=[
            "ciclo contable", "pasos para resolver", "como resuelvo un caso", "orden de los pasos",
            "por donde empiezo", "como empiezo",
        ],
        palabras=["ciclo", "pasos", "resolver", "empiezo", "orden"],
        texto="""## El ciclo contable, paso a paso

Así se resuelve cualquier caso:

1. **Lee el enunciado y separa las operaciones.** Una por una, con su fecha.
2. **Arma el plan de cuentas** con las cuentas que vas a necesitar.
3. **Registra el asiento de apertura** si el enunciado da un inventario inicial.
4. **Registra cada operación.** Pregúntate siempre: ¿qué entra y qué sale? El que entra va
   al Debe si es activo o gasto; el que sale, al Haber.
5. **Asiento de ajuste del costo de ventas** al cierre, con la existencia final.
6. **Revisa el Balance de Comprobación.** Si Debe ≠ Haber, hay un error de registro.
7. **Lee el Estado de Resultados** y el **Balance General**.

En esta aplicación los pasos 6 y 7 son automáticos: apenas registras los asientos, los cinco
reportes ya están listos.

*Si quieres, dime «cómo está mi caso» y te digo en qué paso vas.*""",
    ),
    Ficha(
        clave="letras",
        titulo="Letras de cambio",
        frases=["letras de cambio", "letras por cobrar", "letras por pagar", "que son las letras"],
        palabras=["letras", "letra", "cambio", "cobrar", "pagar"],
        texto="""## Letras de cambio

Una letra es una promesa de pago por escrito. En contabilidad es simplemente una cuenta por
cobrar o por pagar **documentada**.

- Si **tú aceptas** letras al comprar → **Letras por Pagar** (pasivo).
- Si **tu cliente acepta** letras al comprarte → **Letras por Cobrar** (activo).

Cuando se cobra o se paga una letra, no hay ingreso ni gasto: solo cambia de cuenta.

Cobras dos letras de 70,800 cada una:

| Código | Cuenta | Debe | Haber |
| --- | --- | ---: | ---: |
| 102 | Banco | 141,600.00 | 0.00 |
| 104 | Letras por Cobrar | 0.00 | 141,600.00 |

El patrimonio no se mueve: cambiaste un activo por otro.""",
    ),
    Ficha(
        clave="flujo",
        titulo="Cómo se movió el dinero",
        frases=[
            "flujo de efectivo", "flujo de caja", "como se movio el dinero",
            "movimientos de dinero", "en que se gasto", "a donde se fue la plata",
            "entradas y salidas", "por que tengo menos plata", "cash flow",
            "de donde salio el dinero", "movimientos de caja",
        ],
        palabras=["flujo", "movio", "movimientos", "entradas", "salidas", "gasto"],
        vivo=_flujo_de_efectivo,
    ),
    Ficha(
        clave="conclusiones",
        titulo="Conclusiones del caso",
        frases=[
            "conclusiones", "conclusion", "analiza el caso", "analisis del caso", "analizame",
            "interpreta", "interpretacion", "que opinas", "como le fue", "como le fue a la",
            "resumen ejecutivo", "que concluyes", "dame conclusiones", "analisis financiero",
            "que significan los resultados", "interpretacion de resultados",
        ],
        palabras=["conclusiones", "conclusion", "analisis", "analiza", "interpreta",
                  "interpretacion", "opinas", "concluyes"],
        vivo=_conclusiones,
    ),
    Ficha(
        clave="parametros",
        titulo="Las tasas que uso",
        frases=[
            "que tasa usas", "cual es la tasa que usas", "cual es la tasa", "que tasa aplicas",
            "que tasa usa", "con que tasa", "que igv usas", "que igv aplicas", "con que igv",
            "que porcentaje usas", "que impuesto aplicas", "que impuesto usas",
            "con que numeros trabajas", "que tasas manejas", "como redondeas",
            "cuantos decimales", "que tasa tienes",
        ],
        palabras=["tasa", "tasas", "usas", "aplicas", "porcentaje", "redondeas", "decimales"],
        vivo=_parametros,
    ),
    Ficha(
        clave="como-funciona",
        titulo="Cómo funciona la página",
        frases=[
            "como funciona", "como trabaja", "que hace la pagina", "que hace el sistema",
            "de que trata", "como esta hecha", "que puedo hacer aqui", "para que sirve esta",
            "como se usa", "explicame la pagina", "como opera",
        ],
        palabras=["funciona", "trabaja", "pagina", "sistema", "sirve"],
        texto="""## Cómo funciona

Tú registras **asientos** y la aplicación calcula todo lo demás. No hay nada que llenar
dos veces ni totales que se guarden aparte: los cinco reportes se arman cada vez a partir
de tus asientos, así que nunca quedan desfasados.

El orden de trabajo:

1. **Casos** — un caso es una empresa con su plan de cuentas y sus asientos. Puedes tener
   varios y cambiar entre ellos.
2. **Plan de Cuentas** — las cuentas con su código, nombre y tipo. El tipo decide de qué
   lado suma cada cuenta y en qué bloque del Balance General aparece.
3. **Registrar Asiento** — fecha, glosa y las líneas. Solo se guarda si Debe = Haber.
   También puedes importarlos desde Excel, o pegarme el enunciado y yo los armo.
4. **Reportes** — Libro Diario, Libro Mayor, Balance de Comprobación, Estado de Resultados
   y Balance General, todos automáticos.
5. **Descargas** — el PDF con las secciones que elijas, o un Excel con una hoja por reporte.

Las cuentas las hago con decimales exactos y redondeo a 2 decimales, así los totales
cuadran al céntimo. Uso IGV del 18% y, por omisión, 29.5% de impuesto a la renta.""",
    ),
    Ficha(
        clave="que-puedes-hacer",
        titulo="Qué puedo hacer",
        frases=[
            "que puedes hacer", "en que me puedes ayudar", "ayuda", "hola", "buenas",
            "que sabes", "para que sirves", "quien eres",
        ],
        palabras=["ayuda", "hola", "puedes", "sirves", "eres"],
        texto="""Puedo ayudarte con tres cosas:

**1. Revisar tu caso con sus números reales**
- *«¿Cómo está mi caso?»* — resumen con tus cifras
- *«¿Por qué no cuadra?»* — reviso asiento por asiento y te digo dónde está el problema
- *«¿Cuánto IGV tengo?»* y *«¿qué asientos tengo?»*

**2. Usar el sistema**
- Registrar asientos, importar desde Excel, plan de cuentas, PDF y Excel, configuración

**3. Teoría**
- Partida doble, qué va al Debe y al Haber, IGV, impuesto a la renta, costo de ventas,
  letras de cambio, el ciclo contable completo

También hago cuentas: *«cuánto es el IGV de 1,000,000 incluido»*.""",
    ),
]


# ------------------------------------------------------------------ búsqueda

#: Debajo de esto, mejor admitir que no se entendió.
UMBRAL = 2.0


def _elegir_ficha(limpia: str):
    """La mejor ficha para la pregunta, o None si ninguna convence.

    Pedir siempre dos aciertos dejaba fuera las preguntas de una palabra
    («excel», «las cuentas»), que son de las más claras que hay. Si la
    pregunta es corta basta un acierto, siempre que una ficha gane sola.
    """
    puntuadas = sorted(
        ((_puntaje(f, limpia), f) for f in FICHAS), key=lambda par: par[0], reverse=True
    )
    mejor, ficha = puntuadas[0]
    if mejor >= UMBRAL:
        return ficha, puntuadas
    # Con una o dos palabras, un solo acierto basta. Si dos fichas empatan,
    # cualquiera de las dos responde algo razonable: es mejor que no entender.
    con_contenido = [p for p in limpia.split() if p not in VACIAS]
    if len(con_contenido) <= 2 and mejor >= 1.0:
        return ficha, puntuadas
    return None, puntuadas


def misma_raiz(una: str, otra: str) -> bool:
    """¿Son la misma palabra en otra forma?

    Nadie escribe la palabra exacta de la ficha: pregunta «cómo calculas», «el
    cálculo» o «para calcular». Comparar el comienzo cubre singular/plural y
    las conjugaciones sin necesidad de un diccionario.
    """
    if una == otra:
        return True
    corto, largo = sorted((una, otra), key=len)
    if len(corto) >= 4 and largo.startswith(corto):
        return True
    return len(corto) >= 5 and corto[:5] == largo[:5]


#: Palabras que no dicen nada del tema. Se descartan para que lo que decida
#: sean las palabras con contenido y no el largo de la pregunta.
VACIAS = frozenset("""
a al algo alguna alguno ahora aqui asi aun cada como con cosa cual cuales cuando
cuanta cuantas cuanto cuantos de del donde dos e el ella ellas ello ellos en entre
era eran eres es esa esas ese eso esos esta estan estas este esto estos ha hace
hacer hacia hay la las le les lo los me mi mis mucho muy nos o os otra otro para
pero poder por porque que quien se sea ser si sin sobre son su sus tambien te
tendria tener tengo ti tiene tienen tu tus un una uno unos ver y ya yo
""".split())


def _vocabulario(ficha: Ficha) -> Dict[str, float]:
    """Las palabras con contenido de la ficha, con su peso.

    Las frases no sirven solo como coincidencia exacta: sus palabras cuentan
    por separado. Así «¿qué IGV trabajas?» llega aunque la frase escrita sea
    «con qué IGV trabajas», sin tener que anticipar cada forma de preguntarlo.
    Una palabra que viene de una frase pesa más: alguien se tomó el trabajo de
    escribirla dentro de una pregunta entera, no sueltas por si acaso.
    """
    pesos: Dict[str, float] = {palabra: 1.0 for palabra in ficha.palabras}
    for frase in ficha.frases:
        for palabra in frase.split():
            if palabra not in VACIAS:
                # Cuantas más veces la ficha use la palabra, más es su tema:
                # "excel" está en cinco frases de Importar y en dos de Descargas.
                pesos[palabra] = min(2.4, max(pesos.get(palabra, 0), 1.2) + 0.2)
    return pesos


#: Se arma una vez al cargar el módulo, no en cada pregunta.
VOCABULARIOS: Dict[str, Dict[str, float]] = {}


def _puntaje(ficha: Ficha, pregunta: str) -> float:
    puntos = 0.0
    for frase in ficha.frases:
        if frase in pregunta:
            # Una frase entera que calza es mucha más señal que una palabra suelta.
            puntos += 4.0 + len(frase) / 20
    vocabulario = VOCABULARIOS[ficha.clave]
    for palabra in pregunta.split():
        if palabra in VACIAS:
            continue
        pesos = [peso for conocida, peso in vocabulario.items()
                 if misma_raiz(palabra, conocida)]
        if pesos:
            puntos += max(pesos)
    return puntos


VOCABULARIOS.update({ficha.clave: _vocabulario(ficha) for ficha in FICHAS})


def hay_enunciado(pregunta: str, caso: Optional[CasoDominio]) -> bool:
    """¿El texto es un enunciado que se puede convertir en asientos?"""
    if not enunciados.parece_enunciado(pregunta):
        return False
    return bool(enunciados.leer(pregunta, caso or enunciados.CASO_VACIO).asientos)


def responder(pregunta: str, caso: Optional[CasoDominio] = None) -> str:
    """La respuesta en markdown. Nunca lanza: siempre devuelve algo útil."""
    limpia = normalizar(pregunta).strip()
    if not limpia:
        return "Escríbeme una pregunta y te ayudo."

    # Un enunciado pegado se resuelve, no se busca en las fichas.
    if enunciados.parece_enunciado(pregunta):
        return enunciados.resolver(pregunta, caso)

    # "¿cuál es mi utilidad neta?" pide un número suyo, no una ficha de teoría.
    operacion = expresion_aritmetica(pregunta)
    if operacion is not None:
        return _responder_cuenta(operacion)

    indice = cifra_pedida(pregunta)
    if indice is not None:
        if caso is not None:
            return _responder_cifra(indice, caso)
        # Sin caso, solo se interrumpe si preguntó por lo suyo; "impuesto a la
        # renta" a secas es una pregunta de teoría y debe llegar a su ficha.
        if re.search(r"\b(mi|mis|tengo|gane|gano|ganamos|vendi|vendimos)\b", limpia):
            return SIN_CASO

    ficha, puntuadas = _elegir_ficha(limpia)

    # "cuanto es el igv de 1,000,000" -> hace la cuenta con ese número.
    if ficha is not None and ficha.clave in ("igv-teoria", "mi-igv") and _numeros(limpia):
        cuenta = _calcular_igv(caso, limpia)
        if cuenta:
            return cuenta

    if ficha is None:
        cercanas = [f.titulo for _, f in puntuadas[1:4]]
        return "\n".join([
            "No estoy seguro de haber entendido. Puedo responderte sobre:",
            "",
            "- **Tu caso**: «¿cómo está mi caso?», «¿por qué no cuadra?»",
            "- **El sistema**: registrar asientos, importar desde Excel, descargar el PDF",
            "- **Teoría**: partida doble, IGV, costo de ventas, impuesto a la renta",
            "",
            "¿Te sirve alguno de estos? " + ", ".join(cercanas) + ".",
        ])

    if ficha.vivo is not None:
        return ficha.vivo(caso)
    return ficha.texto


def fue_entendida(pregunta: str) -> bool:
    """True si alguna ficha reconoce la pregunta. Lo usa chatbot.py."""
    limpia = normalizar(pregunta).strip()
    if not limpia:
        return False
    if enunciados.parece_enunciado(pregunta):
        return True
    if cifra_pedida(pregunta) is not None or caso_pedido(pregunta) is not None:
        return True
    return _elegir_ficha(limpia)[0] is not None


# ------------------------------------------------------- abrir otro caso

_VERBOS_ABRIR = (
    r"abre|abrir|abras|abreme|abrime|cambia|cambiar|cambiame|pasa|pasar|"
    r"selecciona|seleccionar|carga|cargar|usa|usar|trabajar|muestrame|ponme"
)
#: Lo que viene después del verbo y no nombra a ningún caso guardado.
_NO_ES_NOMBRE = {
    "", "nuevo", "un caso", "un caso nuevo", "uno nuevo", "otro", "otro caso",
    "casos", "los casos", "mis casos", "un caso de ejemplo", "el caso", "caso",
}


def caso_pedido(pregunta: str) -> Optional[str]:
    """El nombre del caso que pide abrir, o None si no está pidiendo eso."""
    limpia = normalizar(pregunta).strip().rstrip("?!. ")
    if not re.search(r"\b(" + _VERBOS_ABRIR + r")\b", limpia):
        return None

    despues = re.search(r"\bcaso\b\s*(?:llamado\s+|de\s+|:\s*)?(.+)$", limpia)
    if despues is None:
        despues = re.search(
            r"\b(?:" + _VERBOS_ABRIR + r")\b\s+(?:a\s+|al\s+|el\s+|la\s+)?(.+)$", limpia
        )
    if despues is None:
        return None

    nombre = despues.group(1).strip(" \"'«»")
    return None if nombre in _NO_ES_NOMBRE else (nombre or None)


# ------------------------------------------------------------- aritmética

#: Solo dígitos, signos y paréntesis: nada que se parezca a código.
SOLO_CUENTAS = re.compile(r"^[\d\s+\-*/().,x×÷]+$")
OPERACION = re.compile(r"\d\s*[-+*/x×÷]\s*[\d(]")

#: Palabras que indican que no es una cuenta suelta sino una pregunta contable.
NO_ES_CUENTA = ("igv", "impuesto", "utilidad", "renta", "asiento", "cuenta", "saldo")


def expresion_aritmetica(pregunta: str) -> Optional[str]:
    """La operación que pide calcular, si la pregunta es solo eso.

    Se trabaja sobre el texto crudo: normalizar() borra «+», «*» y los
    paréntesis, que aquí son justamente lo que hay que conservar.
    """
    plano = unicodedata.normalize("NFD", pregunta.lower())
    limpia = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    limpia = limpia.strip().rstrip("?!=. ")
    for arranque in ("cuanto es", "cuanto hace", "cuanto da", "calcula", "resuelve", "dime"):
        if limpia.startswith(arranque):
            limpia = limpia[len(arranque):].strip()
    if any(palabra in limpia for palabra in NO_ES_CUENTA):
        return None
    if not limpia or not SOLO_CUENTAS.match(limpia) or not OPERACION.search(limpia):
        return None
    return limpia


def calcular(expresion: str) -> Optional[Decimal]:
    """Resuelve la operación con decimales exactos. None si no se puede."""
    import ast

    texto = expresion.replace("x", "*").replace("×", "*").replace("÷", "/")
    # 1,000.50 -> 1000.50; la coma aquí solo separa miles.
    texto = re.sub(r"(?<=\d),(?=\d{3}\b)", "", texto)

    permitidos = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                  ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)

    def resolver(nodo):
        if isinstance(nodo, ast.Expression):
            return resolver(nodo.body)
        if isinstance(nodo, ast.Constant):
            if isinstance(nodo.value, bool) or not isinstance(nodo.value, (int, float)):
                raise ValueError
            return Decimal(str(nodo.value))
        if isinstance(nodo, ast.UnaryOp):
            valor = resolver(nodo.operand)
            return -valor if isinstance(nodo.op, ast.USub) else valor
        if isinstance(nodo, ast.BinOp):
            izq, der = resolver(nodo.left), resolver(nodo.right)
            if isinstance(nodo.op, ast.Add):
                return izq + der
            if isinstance(nodo.op, ast.Sub):
                return izq - der
            if isinstance(nodo.op, ast.Mult):
                return izq * der
            if isinstance(nodo.op, ast.Div):
                if der == 0:
                    raise ZeroDivisionError
                return izq / der
        raise ValueError

    try:
        arbol = ast.parse(texto, mode="eval")
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, permitidos):
                return None
        resultado = resolver(arbol)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError, ArithmeticError):
        return None
    return resultado.quantize(CENTIMO) if resultado % 1 else resultado.quantize(Decimal("1"))


def _responder_cuenta(expresion: str) -> str:
    resultado = calcular(expresion)
    if resultado is None:
        return (
            f"No pude resolver «{expresion}». Puedo con sumas, restas, "
            "multiplicaciones y divisiones, por ejemplo `1+1` o `(400000*1.18)/2`."
        )
    return f"`{expresion}` = **{resultado:,}**".replace(",", " ")


# ------------------------------------------------------- generar un caso

_PIDE_CASO = (
    "genera un caso", "generame un caso", "genera un enunciado", "crea un caso",
    "creame un caso", "inventa un caso", "inventame un caso", "inventa un enunciado",
    "dame un caso", "damelo al azar", "caso al azar", "caso aleatorio",
    "caso de prueba", "un ejercicio", "inventa un ejercicio", "genera un ejercicio",
    "dame un ejercicio", "crea un ejercicio", "caso random", "generar caso",
    "un caso nuevo al azar", "proponme un caso",
)


def pide_caso_nuevo(pregunta: str) -> bool:
    """¿Está pidiendo que se invente un caso?"""
    limpia = normalizar(pregunta).strip()
    if any(frase in limpia for frase in _PIDE_CASO):
        return True
    # "genera / inventa / crea ... un caso" con palabras en medio.
    return bool(
        re.search(r"\b(genera|generame|crea|creame|inventa|inventame|proponme|dame)\b", limpia)
        and re.search(r"\b(caso|enunciado|ejercicio)\b", limpia)
        and re.search(r"\b(azar|aleatorio|random|nuevo|prueba|practicar|practica)\b", limpia)
    )
