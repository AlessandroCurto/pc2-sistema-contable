"""Asistente del Sistema y Gestión Financiera.

Habla con Claude. Lo que lo hace útil no es el modelo sino el contexto: a cada
pregunta se le adjunta el caso que el usuario tiene abierto (su plan de cuentas,
sus asientos y lo que el motor contable ya calculó), así el asistente responde
sobre los números reales en pantalla y no en abstracto.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Dict, Iterator, List, Optional

from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.balance_general import construir_balance_general
from ..dominio.cuentas import ETIQUETA_TIPO, ordenar_cuentas
from ..dominio.estado_resultados import construir_estado_resultados
from ..dominio.tipos import Caso as CasoDominio
from . import asistente

#: Tope de asientos que se mandan en detalle. Por encima, se resumen.
MAX_ASIENTOS = 60

MODELO = os.environ.get("CHATBOT_MODELO", "claude-sonnet-5-5")
MAX_TOKENS = 1600


class ChatbotNoConfigurado(RuntimeError):
    """No hay ANTHROPIC_API_KEY en el entorno."""


INSTRUCCIONES = """Eres el asistente del "Sistema y Gestión Financiera", una aplicación web \
de contabilidad para estudiantes universitarios en Perú. Respondes siempre en español, \
con el tono de un buen profesor: claro, directo y paciente.

Ayudas en tres cosas:

1. RESOLVER CASOS CONTABLES. Si el usuario pega un enunciado, lo resuelves paso a paso: \
qué cuentas se afectan, de qué lado y por qué. Cuando des un asiento, usa una tabla con \
columnas Código, Cuenta, Debe, Haber, y verifica en voz alta que los totales coinciden.

2. USAR LA APLICACIÓN. Conoces sus pantallas:
- Casos: crear un caso (empresa + plan de cuentas), abrirlo, importar/exportar JSON, cargar ejemplos.
- Plan de Cuentas: agregar, editar y eliminar cuentas. Una cuenta con movimientos no se puede eliminar.
- Registrar Asiento: fecha, glosa y líneas. Hay dos modos de llenado: Debe/Haber directo, o signo (+/-) \
  y monto (el lado sale del tipo de cuenta). El asiento solo se guarda si Debe = Haber.
- Importar asientos desde Excel o CSV: columnas numero, fecha, glosa, codigo, debe, haber. Las filas con \
  el mismo numero forman un asiento. Acepta alias (Nro, Cargo, Abono) y fechas dd/mm/aaaa o aaaa-mm-dd. \
  Hay un botón para descargar la plantilla. Los asientos que no cuadran se informan uno por uno.
- Libro Diario (con filtros por texto y por cuenta), Libro Mayor, Balance de Comprobación, \
  Estado de Resultados y Balance General.
- Descargas: reporte PDF (se eligen las secciones) y Excel con una hoja por reporte.
- Configuración: razón social, RUC, moneda, período, tasa del impuesto a la renta y la casilla \
  "el impuesto afecta al patrimonio".

3. TEORÍA. Partida doble, naturaleza de cada tipo de cuenta, el ciclo contable completo, \
los estados financieros y su lectura.

REGLAS DE CONTABILIDAD QUE DEBES RESPETAR (Perú):
- Activo y Gasto: naturaleza deudora (aumentan en el Debe).
- Pasivo, Patrimonio e Ingreso: naturaleza acreedora (aumentan en el Haber).
- IGV 18%. Si un importe "incluye IGV", la base es importe / 1.18 y el IGV es la diferencia. \
  Si el importe es "más IGV", el IGV es importe * 0.18.
- IGV de compras = IGV Crédito Fiscal (activo). IGV de ventas = IGV Débito Fiscal (pasivo).
- Impuesto a la renta de tercera categoría: 29.5% sobre la utilidad, solo si es positiva.
- El impuesto a la renta no es patrimonio: la utilidad NETA va al patrimonio y el impuesto queda \
  como "Impuesto a la renta por pagar" en el pasivo. Esta aplicación lo hace así cuando la casilla \
  "el impuesto afecta al patrimonio" está marcada, que es lo correcto.
- Costo de ventas por diferencia de inventarios = inventario inicial + compras - inventario final.

CÓMO RESPONDES:
- Vas al grano. Nada de "¡Claro! Con gusto te ayudo con eso."
- Markdown: **negritas**, listas, tablas y `código`. Sin títulos de nivel 1.
- Respuestas cortas para preguntas cortas. Solo te extiendes al resolver un caso.
- Si el usuario tiene un caso abierto, úsalo: cita sus cuentas y sus cifras reales.
- Si te falta un dato del enunciado, lo pides en vez de inventarlo.
- Si algo no se puede hacer en la aplicación, lo dices claro en vez de inventar un botón."""

SIN_CASO = """ESTADO ACTUAL: el usuario no tiene ningún caso abierto.
Si su pregunta necesita un caso, recuérdale que primero debe abrirlo o crearlo en la pantalla Casos \
(también puede cargar uno de ejemplo desde ahí)."""


def _num(valor: Decimal) -> str:
    return f"{valor:,.2f}"


def _contexto_del_caso(caso: Optional[CasoDominio]) -> str:
    """Convierte el caso abierto en texto para el modelo."""
    if caso is None:
        return SIN_CASO

    empresa = caso.empresa
    simbolo = empresa.simbolo_moneda
    lineas: List[str] = ["ESTADO ACTUAL: el usuario tiene este caso abierto en pantalla.", ""]

    periodo = (
        f"{empresa.periodo_inicio:%d/%m/%Y} al {empresa.periodo_fin:%d/%m/%Y}"
        if empresa.periodo_inicio and empresa.periodo_fin
        else "sin definir"
    )
    lineas += [
        "## Empresa",
        f"- Razón social: {empresa.nombre}",
        f"- RUC: {empresa.ruc or 'sin RUC'}",
        f"- Moneda: {simbolo}",
        f"- Período: {periodo}",
        f"- Tasa del impuesto a la renta: {empresa.tasa_impuesto_renta}%",
        "- El impuesto afecta al patrimonio: "
        + ("sí (la utilidad neta va al patrimonio y el impuesto al pasivo)"
           if empresa.impuesto_afecta_patrimonio
           else "no (el patrimonio muestra la utilidad antes de impuesto)"),
        "",
    ]

    cuentas = ordenar_cuentas(caso.cuentas)
    if cuentas:
        lineas.append(f"## Plan de cuentas ({len(cuentas)} cuentas)")
        lineas.append("| Código | Cuenta | Tipo |")
        lineas.append("| --- | --- | --- |")
        for cuenta in cuentas:
            lineas.append(
                f"| {cuenta.codigo} | {cuenta.nombre} | {ETIQUETA_TIPO.get(cuenta.tipo, cuenta.tipo)} |"
            )
        lineas.append("")
    else:
        lineas += ["## Plan de cuentas", "Vacío: el caso todavía no tiene cuentas.", ""]

    por_id = {cuenta.id: cuenta for cuenta in caso.cuentas}
    asientos = sorted(caso.asientos, key=lambda a: (a.fecha, a.numero))
    if asientos:
        mostrados = asientos[:MAX_ASIENTOS]
        titulo = f"## Asientos registrados ({len(asientos)})"
        if len(asientos) > MAX_ASIENTOS:
            titulo += f" — se listan los {MAX_ASIENTOS} primeros"
        lineas.append(titulo)
        for asiento in mostrados:
            lineas.append(
                f"\nAsiento {asiento.numero} — {asiento.fecha:%d/%m/%Y} — {asiento.glosa}"
            )
            lineas.append("| Código | Cuenta | Debe | Haber |")
            lineas.append("| --- | --- | ---: | ---: |")
            for linea in asiento.lineas:
                cuenta = por_id.get(linea.cuenta_id)
                codigo = cuenta.codigo if cuenta else "?"
                nombre = cuenta.nombre if cuenta else "(cuenta eliminada)"
                lineas.append(f"| {codigo} | {nombre} | {_num(linea.debe)} | {_num(linea.haber)} |")
        lineas.append("")
    else:
        lineas += ["## Asientos registrados", "Ninguno todavía.", ""]

    # Lo que el motor ya calculó: así el asistente no rehace la aritmética.
    balance = construir_balance_comprobacion(caso)
    estado = construir_estado_resultados(caso)
    general = construir_balance_general(caso)
    lineas += [
        "## Cifras que la aplicación ya calculó (son las correctas, no las recalcules)",
        f"- Balance de comprobación: total Debe {simbolo} {_num(balance.total_debe)}, "
        f"total Haber {simbolo} {_num(balance.total_haber)} "
        + ("— cuadrado." if balance.cuadrado else "— NO CUADRA."),
        f"- Ventas netas: {simbolo} {_num(estado.ventas_netas)}",
        f"- Utilidad bruta: {simbolo} {_num(estado.utilidad_bruta)}",
        f"- Resultado antes del impuesto: {simbolo} {_num(estado.resultado_antes_impuesto)}",
        f"- Impuesto a la renta ({estado.tasa_impuesto}%): {simbolo} {_num(estado.impuesto)}",
        f"- Utilidad neta: {simbolo} {_num(estado.utilidad_neta)}",
        f"- Total activo: {simbolo} {_num(general.total_activo)}",
        f"- Total pasivo: {simbolo} {_num(general.total_pasivo)}",
        f"- Total patrimonio: {simbolo} {_num(general.total_patrimonio)}",
        "- Balance general: "
        + ("cuadrado (Activo = Pasivo + Patrimonio)." if general.cuadrado
           else f"NO CUADRA, diferencia de {simbolo} {_num(general.diferencia)}."),
    ]
    if general.impuesto_por_pagar > 0:
        lineas.append(
            f"- Impuesto a la renta por pagar (en el pasivo): {simbolo} "
            f"{_num(general.impuesto_por_pagar)}"
        )
    return "\n".join(lineas)


def _cliente():
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        raise ChatbotNoConfigurado(
            "El asistente todavía no está configurado: falta la clave ANTHROPIC_API_KEY."
        )
    import anthropic

    return anthropic.Anthropic(api_key=clave)


def _sistema(caso: Optional[CasoDominio]) -> List[Dict]:
    """System prompt en dos bloques: el fijo se cachea, el del caso cambia."""
    return [
        {
            "type": "text",
            "text": INSTRUCCIONES,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": _contexto_del_caso(caso)},
    ]


def hay_api() -> bool:
    """¿Está puesta la clave? Sin ella el asistente funciona igual, pero local."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def responder_en_vivo(
    mensajes: List[Dict[str, str]],
    caso: Optional[CasoDominio] = None,
    permitir_api: bool = False,
) -> Iterator[str]:
    """Devuelve la respuesta por pedazos, para escribirla en pantalla al vuelo.

    Primero contesta el asistente local, que no cuesta nada y para las preguntas
    que conoce es más exacto (lee el caso y usa el motor contable). La vista
    decide en `permitir_api` si esta pregunta puede llegar al modelo: solo
    cuando lo local no la entendió, hay clave y al sitio le queda cupo del día.
    """
    pregunta = mensajes[-1]["content"] if mensajes else ""
    local = asistente.responder(pregunta, caso)

    if permitir_api:
        try:
            yield from _responder_con_api(mensajes, caso)
            return
        except Exception:
            pass  # si la API falla, queda la respuesta local

    # En trozos, para que la pantalla lo escriba como una conversación.
    for parrafo in local.split("\n\n"):
        yield parrafo + "\n\n"


def _responder_con_api(
    mensajes: List[Dict[str, str]], caso: Optional[CasoDominio]
) -> Iterator[str]:
    cliente = _cliente()
    with cliente.messages.stream(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=_sistema(caso),
        messages=mensajes,
    ) as flujo:
        for pedazo in flujo.text_stream:
            yield pedazo


def responder(mensajes: List[Dict[str, str]], caso: Optional[CasoDominio] = None) -> str:
    """Respuesta completa de una sola vez. La usan las pruebas."""
    return "".join(responder_en_vivo(mensajes, caso))
