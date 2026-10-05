"""Reporte financiero en PDF con ReportLab.

Es el equivalente del jsPDF de la versión web: misma portada negra, mismas
tablas con cabecera negra y texto amarillo, y las mismas cinco secciones.
La diferencia es que aquí el PDF se arma en el servidor y se descarga ya hecho.

Dos detalles de ReportLab que conviene recordar:

- El pie dice "Página N de M", y el total de páginas solo se conoce al final.
  Por eso el pie se dibuja en una segunda pasada, con la clase _Lienzo.
- La banda negra de cada sección se dibuja cuando empieza la página, antes de
  acomodar el contenido. Por eso el título se cambia con _TituloSeccion justo
  antes del salto de página, no después.
"""

from __future__ import annotations

import io
from datetime import date
from functools import partial
from typing import List, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas as reportlab_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.balance_general import construir_balance_general
from ..dominio.estado_resultados import construir_estado_resultados
from ..dominio.formato import formatear_fecha, formatear_numero
from ..dominio.libro_diario import construir_libro_diario
from ..dominio.libro_mayor import construir_libro_mayor
from ..dominio.numeros import es_cero
from ..dominio.tipos import Caso, Naturaleza

#: Secciones del reporte, en el orden en que salen en el PDF.
SECCIONES: List[Tuple[str, str]] = [
    ("libroDiario", "Libro Diario"),
    ("libroMayor", "Libro Mayor"),
    ("balanceComprobacion", "Balance de Comprobación"),
    ("estadoResultados", "Estado de Resultados"),
    ("balanceGeneral", "Balance General"),
]

CLAVES_SECCION = [clave for clave, _ in SECCIONES]
ETIQUETAS_SECCION = dict(SECCIONES)

#: ReportLab ya mide en puntos: 1 unidad = 1 pt. Se deja el nombre para que
#: las medidas se lean igual que en la version web (40 * pt, 58 * pt...).
pt = 1

NEGRO = colors.Color(17 / 255, 17 / 255, 17 / 255)
GRIS = colors.Color(241 / 255, 244 / 255, 248 / 255)
AMARILLO = colors.Color(242 / 255, 194 / 255, 0)
TEXTO = colors.Color(20 / 255, 24 / 255, 31 / 255)
ATENUADO = colors.Color(120 / 255, 127 / 255, 138 / 255)
LINEA = colors.Color(0.85, 0.87, 0.9)

MARGEN = 40 * pt
ALTO_CABECERA = 58 * pt
ALTO_PORTADA = 200 * pt
SEPARADOR = "  ·  "

ESTILO_NOTA = ParagraphStyle(
    "nota", fontName="Helvetica", fontSize=10, leading=15, textColor=TEXTO
)


class _Lienzo(reportlab_canvas.Canvas):
    """Lienzo que guarda las páginas para escribir el pie con el total."""

    def __init__(self, *args, empresa: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        self._paginas = []

    def showPage(self):  # noqa: N802 (nombre de ReportLab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._pie(total)
            super().showPage()
        super().save()

    def _pie(self, total: int):
        self.setFont("Helvetica", 8)
        self.setFillColor(ATENUADO)
        texto = (
            "Contabilidad UNI"
            + SEPARADOR
            + self.empresa
            + SEPARADOR
            + "Página "
            + str(self.getPageNumber())
            + " de "
            + str(total)
        )
        self.drawString(MARGEN, 20 * pt, texto)


class _Documento(BaseDocTemplate):
    """Documento con dos plantillas de página: la portada y las secciones."""

    def __init__(self, destino, empresa: str, periodo: str, simbolo: str, ruc: str):
        super().__init__(
            destino,
            pagesize=A4,
            leftMargin=MARGEN,
            rightMargin=MARGEN,
            topMargin=MARGEN,
            bottomMargin=MARGEN,
            title="Reporte Financiero Completo",
            author="Contabilidad UNI",
        )
        self.empresa = empresa
        self.periodo = periodo
        self.simbolo = simbolo
        self.ruc = ruc
        self.titulo_seccion = ""

        ancho_util = self.pagesize[0] - 2 * MARGEN
        alto = self.pagesize[1]

        portada = Frame(
            MARGEN,
            MARGEN,
            ancho_util,
            alto - ALTO_PORTADA - 40 * pt - MARGEN,
            id="portada",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        contenido = Frame(
            MARGEN,
            MARGEN + 12 * pt,
            ancho_util,
            alto - ALTO_CABECERA - 22 * pt - MARGEN - 12 * pt,
            id="contenido",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )

        self.addPageTemplates(
            [
                PageTemplate(id="portada", frames=[portada], onPage=self._portada),
                PageTemplate(id="seccion", frames=[contenido], onPage=self._cabecera),
            ]
        )

    def _portada(self, lienzo, documento):
        ancho, alto = self.pagesize
        lienzo.saveState()
        lienzo.setFillColor(NEGRO)
        lienzo.rect(0, alto - ALTO_PORTADA, ancho, ALTO_PORTADA, stroke=0, fill=1)
        lienzo.setFillColor(AMARILLO)
        lienzo.rect(0, alto - ALTO_PORTADA - 4 * pt, ancho, 4 * pt, stroke=0, fill=1)
        lienzo.setFillColor(colors.white)
        lienzo.setFont("Helvetica-Bold", 26)
        lienzo.drawString(MARGEN, alto - 96 * pt, "Reporte Financiero Completo")
        lienzo.setFont("Helvetica", 13)
        lienzo.drawString(MARGEN, alto - 124 * pt, self.empresa)
        lienzo.setFont("Helvetica", 10)
        lienzo.drawString(MARGEN, alto - 144 * pt, self.ruc)
        lienzo.drawString(MARGEN, alto - 160 * pt, self.periodo)
        lienzo.restoreState()

    def _cabecera(self, lienzo, documento):
        ancho, alto = self.pagesize
        lienzo.saveState()
        lienzo.setFillColor(NEGRO)
        lienzo.rect(0, alto - ALTO_CABECERA, ancho, ALTO_CABECERA, stroke=0, fill=1)
        lienzo.setFillColor(AMARILLO)
        lienzo.rect(0, alto - ALTO_CABECERA - 4 * pt, ancho, 4 * pt, stroke=0, fill=1)
        lienzo.setFillColor(colors.white)
        lienzo.setFont("Helvetica-Bold", 15)
        lienzo.drawString(MARGEN, alto - 27 * pt, self.titulo_seccion)
        lienzo.setFont("Helvetica", 9)
        detalle = (
            self.empresa + SEPARADOR + self.periodo + SEPARADOR + "Importes en " + self.simbolo
        )
        lienzo.drawString(MARGEN, alto - 44 * pt, detalle)
        lienzo.restoreState()


class _TituloSeccion(Spacer):
    """Marca invisible: cambia el título de la banda negra de la página siguiente.

    Va antes del PageBreak porque la banda se dibuja al empezar la página.
    """

    def __init__(self, documento: _Documento, titulo: str):
        super().__init__(1, 0)
        self.documento = documento
        self.titulo = titulo

    def wrap(self, ancho, alto):
        self.documento.titulo_seccion = self.titulo
        return (0, 0)

    def draw(self):
        self.documento.titulo_seccion = self.titulo


def _tabla(
    cabeza: Sequence[str],
    cuerpo: Sequence[Sequence[str]],
    anchos=None,
    alinear_derecha: Sequence[int] = (),
    resaltar: Sequence[int] = (),
):
    """Tabla con cabecera negra y texto amarillo, como en la versión web.

    resaltar son los índices de filas del cuerpo que van en negrita (totales).
    """
    datos = [list(cabeza)] + [list(fila) for fila in cuerpo]
    tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
        ("TEXTCOLOR", (0, 0), (-1, 0), AMARILLO),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXTO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINEA),
    ]
    for columna in alinear_derecha:
        estilos.append(("ALIGN", (columna, 0), (columna, -1), "RIGHT"))
    for fila in resaltar:
        estilos.append(("FONTNAME", (0, fila + 1), (-1, fila + 1), "Helvetica-Bold"))
    tabla.setStyle(TableStyle(estilos))
    return tabla


def _importe(valor) -> str:
    return formatear_numero(valor)


def periodo_de(caso: Caso) -> str:
    """Del 01/01/2024 al 31/12/2024, o el aviso de que falta definirlo."""
    empresa = caso.empresa
    if empresa.periodo_inicio and empresa.periodo_fin:
        return (
            "Del "
            + formatear_fecha(empresa.periodo_inicio)
            + " al "
            + formatear_fecha(empresa.periodo_fin)
        )
    return "Período no definido"


def generar_reporte_pdf(caso: Caso, secciones: Sequence[str], nombre_empresa: str = "") -> bytes:
    """Arma el reporte completo y devuelve los bytes del PDF."""
    elegidas = [clave for clave in CLAVES_SECCION if clave in secciones]
    if not elegidas:
        raise ValueError("Elige al menos un reporte para incluir en el PDF.")

    empresa = (nombre_empresa or "").strip() or caso.empresa.nombre
    simbolo = caso.empresa.simbolo_moneda
    periodo = periodo_de(caso)

    destino = io.BytesIO()
    documento = _Documento(
        destino,
        empresa=empresa,
        periodo=periodo,
        simbolo=simbolo,
        ruc=("RUC " + caso.empresa.ruc) if caso.empresa.ruc else "Sin RUC registrado",
    )

    historia = [
        Spacer(1, 18 * pt),
        Paragraph(
            "Generado el " + formatear_fecha(date.today()) + " con Contabilidad UNI.", ESTILO_NOTA
        ),
        Spacer(1, 8 * pt),
        Paragraph(
            "Contenido: " + ", ".join(ETIQUETAS_SECCION[clave] for clave in elegidas) + ".",
            ESTILO_NOTA,
        ),
    ]

    for clave in elegidas:
        historia.append(NextPageTemplate("seccion"))
        historia.append(_TituloSeccion(documento, ETIQUETAS_SECCION[clave]))
        historia.append(PageBreak())
        historia.extend(_seccion(clave, caso, simbolo))

    documento.build(historia, canvasmaker=partial(_Lienzo, empresa=empresa))
    return destino.getvalue()


def _seccion(clave: str, caso: Caso, simbolo: str):
    if clave == "libroDiario":
        return _seccion_libro_diario(caso)
    if clave == "libroMayor":
        return _seccion_libro_mayor(caso)
    if clave == "balanceComprobacion":
        return _seccion_balance_comprobacion(caso)
    if clave == "estadoResultados":
        return _seccion_estado_resultados(caso, simbolo)
    return _seccion_balance_general(caso, simbolo)


def _seccion_libro_diario(caso: Caso):
    diario = construir_libro_diario(caso)
    cuerpo: List[List[str]] = []
    resaltar: List[int] = []
    for item in diario.asientos:
        for fila in item.filas:
            cuenta = fila.cuenta
            cuerpo.append(
                [
                    "#" + str(item.asiento.numero) if fila.primera else "",
                    formatear_fecha(item.asiento.fecha) if fila.primera else "",
                    (cuenta.codigo + " " + cuenta.nombre) if cuenta else "",
                    item.asiento.glosa if fila.primera else "",
                    _importe(fila.debe) if not es_cero(fila.debe) else "",
                    _importe(fila.haber) if not es_cero(fila.haber) else "",
                ]
            )
        resaltar.append(len(cuerpo))
        cuerpo.append(
            [
                "",
                "",
                "Totales del asiento",
                "",
                _importe(item.total_debe),
                _importe(item.total_haber),
            ]
        )
    resaltar.append(len(cuerpo))
    cuerpo.append(
        ["", "", "TOTAL GENERAL", "", _importe(diario.total_debe), _importe(diario.total_haber)]
    )
    anchos = [34 * pt, 58 * pt, 130 * pt, 153 * pt, 70 * pt, 70 * pt]
    cabeza = ["N.", "Fecha", "Cuenta", "Glosa", "Debe", "Haber"]
    return [_tabla(cabeza, cuerpo, anchos, (4, 5), resaltar)]


def _seccion_libro_mayor(caso: Caso):
    mayor = construir_libro_mayor(caso)
    partes = []
    anchos = [58 * pt, 34 * pt, 165 * pt, 66 * pt, 66 * pt, 66 * pt]
    for grupo in mayor.grupos:
        for item in grupo.cuentas:
            cuerpo = [
                [
                    formatear_fecha(movimiento.fecha),
                    "#" + str(movimiento.numero),
                    movimiento.glosa,
                    _importe(movimiento.debe) if not es_cero(movimiento.debe) else "",
                    _importe(movimiento.haber) if not es_cero(movimiento.haber) else "",
                    _importe(movimiento.saldo),
                ]
                for movimiento in item.movimientos
            ]
            cuerpo.append(
                [
                    "Totales",
                    "",
                    "Saldo deudor"
                    if item.naturaleza_saldo == Naturaleza.DEUDOR
                    else "Saldo acreedor",
                    _importe(item.total_debe),
                    _importe(item.total_haber),
                    _importe(item.saldo),
                ]
            )
            cabeza = [
                item.cuenta.codigo + " - " + item.cuenta.nombre + " (" + grupo.etiqueta + ")",
                "",
                "",
                "Debe",
                "Haber",
                "Saldo",
            ]
            partes.append(_tabla(cabeza, cuerpo, anchos, (3, 4, 5), [len(cuerpo) - 1]))
            partes.append(Spacer(1, 18 * pt))
    return partes


def _seccion_balance_comprobacion(caso: Caso):
    balance = construir_balance_comprobacion(caso)
    cuerpo = [
        [
            fila.cuenta.codigo,
            fila.cuenta.nombre,
            _importe(fila.suma_debe),
            _importe(fila.suma_haber),
            _importe(fila.saldo_deudor) if not es_cero(fila.saldo_deudor) else "",
            _importe(fila.saldo_acreedor) if not es_cero(fila.saldo_acreedor) else "",
        ]
        for fila in balance.filas
    ]
    cuerpo.append(
        [
            "",
            "TOTALES",
            _importe(balance.total_debe),
            _importe(balance.total_haber),
            _importe(balance.total_deudor),
            _importe(balance.total_acreedor),
        ]
    )
    anchos = [50 * pt, 135 * pt, 70 * pt, 70 * pt, 70 * pt, 70 * pt]
    cabeza = ["Código", "Cuenta", "Suma Debe", "Suma Haber", "Saldo Deudor", "Saldo Acreedor"]
    nota = (
        "El balance de comprobación está cuadrado."
        if balance.cuadrado
        else "Atención: el balance de comprobación no está cuadrado."
    )
    return [
        _tabla(cabeza, cuerpo, anchos, (2, 3, 4, 5), [len(cuerpo) - 1]),
        Spacer(1, 16 * pt),
        Paragraph(nota, ESTILO_NOTA),
    ]


def _seccion_estado_resultados(caso: Caso, simbolo: str):
    estado = construir_estado_resultados(caso)
    cuerpo = []
    resaltar = []
    for fila in estado.filas:
        if fila.clase == "detalle" and es_cero(fila.monto):
            continue
        prefijo = "(-) " if fila.signo == "-" else ""
        if fila.clase != "detalle":
            resaltar.append(len(cuerpo))
        cuerpo.append([prefijo + fila.etiqueta, _importe(fila.monto)])
    anchos = [355 * pt, 110 * pt]
    return [_tabla(["Concepto", "Importe (" + simbolo + ")"], cuerpo, anchos, (1,), resaltar)]


def _seccion_balance_general(caso: Caso, simbolo: str):
    general = construir_balance_general(caso)
    cuerpo: List[List[str]] = []
    resaltar: List[int] = []
    bloques = [
        general.activo_corriente,
        general.activo_no_corriente,
        general.pasivo_corriente,
        general.pasivo_no_corriente,
        general.patrimonio,
    ]
    for bloque in bloques:
        if not bloque.cuentas:
            continue
        resaltar.append(len(cuerpo))
        cuerpo.append([bloque.etiqueta.upper(), "", ""])
        for detalle in bloque.cuentas:
            cuerpo.append([detalle.cuenta.codigo, detalle.cuenta.nombre, _importe(detalle.monto)])
        resaltar.append(len(cuerpo))
        cuerpo.append(["", "Total " + bloque.etiqueta.lower(), _importe(bloque.total)])

    finales = [
        (
            "Resultado del ejercicio (neto de impuesto)"
            if general.resultado_neto_de_impuesto
            else "Resultado del ejercicio (antes de impuesto)",
            general.resultado_ejercicio,
        ),
        ("TOTAL ACTIVO", general.total_activo),
        ("TOTAL PASIVO", general.total_pasivo),
        ("TOTAL PATRIMONIO", general.total_patrimonio),
        ("TOTAL PASIVO + PATRIMONIO", general.total_pasivo_patrimonio),
    ]
    for etiqueta, monto in finales:
        resaltar.append(len(cuerpo))
        cuerpo.append(["", etiqueta, _importe(monto)])

    anchos = [60 * pt, 295 * pt, 110 * pt]
    nota = (
        "Sí cumple: Total Activo = Total Pasivo + Total Patrimonio."
        if general.cuadrado
        else "Atención: la ecuación contable no cierra."
    )
    cabeza = ["Código", "Concepto", "Importe (" + simbolo + ")"]
    return [
        _tabla(cabeza, cuerpo, anchos, (2,), resaltar),
        Spacer(1, 16 * pt),
        Paragraph(nota, ESTILO_NOTA),
    ]


def nombre_reporte(caso: Caso) -> str:
    """reporte-financiero-cybertec-sa.pdf"""
    limpio: List[str] = []
    for letra in caso.nombre.lower():
        if letra.isalnum():
            limpio.append(letra)
        elif limpio and limpio[-1] != "-":
            limpio.append("-")
    base = "".join(limpio).strip("-") or "caso"
    return "reporte-financiero-" + base + ".pdf"
