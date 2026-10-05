"""Guardar y traer casos: JSON de respaldo e importación de asientos.

El JSON es el mismo respaldo que tenía la versión web, así un caso se puede
llevar de una computadora a otra. La importación de asientos usa lo que leyó
pandas (servicios/excel.py) y valida cada asiento con el motor contable antes
de escribir nada en la base de datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Sequence

from django.db import transaction

from ..dominio import tipos
from ..dominio.asientos import siguiente_numero, validar_asiento
from ..dominio.cuentas import rubro_por_defecto
from ..dominio.formato import formatear_fecha
from ..models import Asiento, Caso, Cuenta, LineaAsiento

VERSION_RESPALDO = 1


# ------------------------------------------------------------------ respaldo


def exportar_json(caso: Caso) -> dict:
    """El caso completo como diccionario listo para guardar en un .json."""
    cuentas = list(caso.cuentas.all())
    asientos = list(caso.asientos.all().prefetch_related("lineas__cuenta"))
    return {
        "version": VERSION_RESPALDO,
        "generadoPor": "Contabilidad UNI (Django)",
        "caso": {
            "nombre": caso.nombre,
            "razonSocial": caso.razon_social,
            "ruc": caso.ruc,
            "simboloMoneda": caso.simbolo_moneda,
            "periodoInicio": caso.periodo_inicio.isoformat() if caso.periodo_inicio else None,
            "periodoFin": caso.periodo_fin.isoformat() if caso.periodo_fin else None,
            "tasaImpuestoRenta": str(caso.tasa_impuesto_renta),
            "impuestoAfectaPatrimonio": caso.impuesto_afecta_patrimonio,
            "cuentas": [
                {
                    "codigo": cuenta.codigo,
                    "nombre": cuenta.nombre,
                    "tipo": cuenta.tipo,
                    "rubro": cuenta.rubro or None,
                }
                for cuenta in cuentas
            ],
            "asientos": [
                {
                    "numero": asiento.numero,
                    "fecha": asiento.fecha.isoformat(),
                    "glosa": asiento.glosa,
                    "lineas": [
                        {
                            "codigo": linea.cuenta.codigo,
                            "debe": str(linea.debe),
                            "haber": str(linea.haber),
                        }
                        for linea in asiento.lineas.all()
                    ],
                }
                for asiento in asientos
            ],
        },
    }


def nombre_respaldo(caso: Caso) -> str:
    from .pdf import nombre_reporte

    return nombre_reporte(caso).replace("reporte-financiero-", "caso-").replace(".pdf", ".json")


def _fecha_iso(valor, donde: str):
    from datetime import date

    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("Falta la fecha en " + donde + ".")
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        raise ValueError("La fecha " + texto + " de " + donde + " no se entiende.")


@transaction.atomic
def importar_json(datos: dict) -> Caso:
    """Crea un caso nuevo a partir de un respaldo. Todo o nada."""
    if not isinstance(datos, dict):
        raise ValueError("El archivo no tiene el formato esperado.")
    cuerpo = datos.get("caso") if isinstance(datos.get("caso"), dict) else datos
    nombre = str(cuerpo.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("El archivo no trae el nombre del caso.")

    caso = Caso.objects.create(
        nombre=nombre[:80],
        razon_social=str(cuerpo.get("razonSocial") or nombre)[:120],
        ruc=str(cuerpo.get("ruc") or "")[:11],
        simbolo_moneda=str(cuerpo.get("simboloMoneda") or "S/")[:5],
        periodo_inicio=_fecha_iso(cuerpo.get("periodoInicio"), "el período")
        if cuerpo.get("periodoInicio")
        else None,
        periodo_fin=_fecha_iso(cuerpo.get("periodoFin"), "el período")
        if cuerpo.get("periodoFin")
        else None,
        tasa_impuesto_renta=Decimal(str(cuerpo.get("tasaImpuestoRenta") or "0")),
        impuesto_afecta_patrimonio=bool(cuerpo.get("impuestoAfectaPatrimonio")),
    )

    por_codigo: Dict[str, Cuenta] = {}
    for fila in cuerpo.get("cuentas") or []:
        codigo = str(fila.get("codigo") or "").strip()
        if not codigo or codigo in por_codigo:
            continue
        tipo = str(fila.get("tipo") or "")
        if tipo not in [item.value for item in tipos.TipoCuenta]:
            raise ValueError("La cuenta " + codigo + " tiene un tipo desconocido: " + tipo)
        rubro = fila.get("rubro") or ""
        if not rubro:
            por_defecto = rubro_por_defecto(tipos.TipoCuenta(tipo))
            rubro = por_defecto.value if por_defecto else ""
        por_codigo[codigo] = Cuenta.objects.create(
            caso=caso,
            codigo=codigo[:12],
            nombre=str(fila.get("nombre") or codigo)[:80],
            tipo=tipo,
            rubro=rubro,
        )

    if not por_codigo:
        raise ValueError("El archivo no trae cuentas.")

    for fila in cuerpo.get("asientos") or []:
        asiento = Asiento.objects.create(
            caso=caso,
            numero=int(fila.get("numero") or 0) or (len(caso.asientos.all()) + 1),
            fecha=_fecha_iso(fila.get("fecha"), "un asiento"),
            glosa=str(fila.get("glosa") or "")[:140],
        )
        for orden, linea in enumerate(fila.get("lineas") or []):
            codigo = str(linea.get("codigo") or "").strip()
            cuenta = por_codigo.get(codigo)
            if cuenta is None:
                raise ValueError(
                    "El asiento " + str(asiento.numero) + " usa la cuenta " + codigo
                    + ", que no está en el plan del archivo."
                )
            LineaAsiento.objects.create(
                asiento=asiento,
                cuenta=cuenta,
                debe=Decimal(str(linea.get("debe") or "0")),
                haber=Decimal(str(linea.get("haber") or "0")),
                orden=orden,
            )

    return caso


# ---------------------------------------------------- importación de asientos


@dataclass
class ResultadoImportacion:
    """Qué se guardó y qué se dejó fuera, para avisarlo en pantalla."""

    importados: int = 0
    errores: List[str] = None

    def __post_init__(self):
        if self.errores is None:
            self.errores = []


def importar_asientos(caso: Caso, leidos: Sequence[dict], crear_cuentas: bool = False):
    """Guarda los asientos leídos de un Excel o CSV.

    Cada asiento se valida con validar_asiento(): los que no cuadran se
    informan y no se guardan. Si crear_cuentas es True, los códigos que no
    están en el plan se crean como activo (el usuario luego los corrige).
    """
    resultado = ResultadoImportacion()
    por_codigo = {cuenta.codigo: cuenta for cuenta in caso.cuentas.all()}
    numero = siguiente_numero([asiento.a_dominio() for asiento in caso.asientos.all()])

    for item in leidos:
        etiqueta = "Asiento " + str(item.get("numero") or "")
        try:
            with transaction.atomic():
                cuentas_linea = []
                for linea in item["lineas"]:
                    codigo = linea["codigo"]
                    cuenta = por_codigo.get(codigo)
                    if cuenta is None:
                        if not crear_cuentas:
                            raise ValueError(
                                "la cuenta " + codigo + " no está en el plan de cuentas"
                            )
                        cuenta = Cuenta.objects.create(
                            caso=caso,
                            codigo=codigo[:12],
                            nombre=codigo,
                            tipo=tipos.TipoCuenta.ACTIVO.value,
                            rubro=tipos.Rubro.CORRIENTE.value,
                        )
                        por_codigo[codigo] = cuenta
                    cuentas_linea.append((cuenta, linea["debe"], linea["haber"]))

                lineas_dominio = [
                    tipos.LineaAsiento(
                        id=str(indice),
                        cuenta_id=str(cuenta.pk),
                        debe=debe,
                        haber=haber,
                    )
                    for indice, (cuenta, debe, haber) in enumerate(cuentas_linea)
                ]
                errores = validar_asiento(
                    item["fecha"],
                    item.get("glosa", ""),
                    lineas_dominio,
                    [cuenta.a_dominio() for cuenta in por_codigo.values()],
                )
                if errores.hay_errores():
                    motivos = [
                        texto
                        for texto in (errores.fecha, errores.glosa, errores.lineas, errores.cuadre)
                        if texto
                    ]
                    motivos.extend(errores.por_linea.values())
                    raise ValueError("; ".join(motivos) or "no cuadra")

                asiento = Asiento.objects.create(
                    caso=caso,
                    numero=numero,
                    fecha=item["fecha"],
                    glosa=str(item.get("glosa") or "")[:140],
                )
                for orden, (cuenta, debe, haber) in enumerate(cuentas_linea):
                    LineaAsiento.objects.create(
                        asiento=asiento, cuenta=cuenta, debe=debe, haber=haber, orden=orden
                    )
                numero += 1
                resultado.importados += 1
        except ValueError as error:
            fecha = item.get("fecha")
            detalle = formatear_fecha(fecha) if fecha else "sin fecha"
            resultado.errores.append(etiqueta + " (" + detalle + "): " + str(error))

    if resultado.importados:
        caso.save(update_fields=["actualizado_en"])
    return resultado
