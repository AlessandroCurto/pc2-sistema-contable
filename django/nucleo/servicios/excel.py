"""Excel con pandas: exportar los cinco reportes e importar asientos.

En la versión web esto no existía (el navegador solo armaba el PDF). Aquí, con
Python, conviene usar pandas: cada reporte es una tabla, y pandas las escribe
en un libro de Excel con una hoja por reporte. Lo mismo al revés: el profesor
suele dar el caso en una hoja de cálculo, así que se puede importar.

Reglas que se mantienen:

- Los cálculos siguen saliendo del dominio (Decimal). pandas solo acomoda las
  tablas y escribe el archivo, no hace contabilidad.
- Al importar, cada asiento pasa por validar_asiento(): si el Debe no es igual
  al Haber, no entra nada.
"""

from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Sequence

import pandas as pd

from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.balance_general import construir_balance_general
from ..dominio.estado_resultados import construir_estado_resultados
from ..dominio.formato import formatear_fecha
from ..dominio.libro_diario import construir_libro_diario
from ..dominio.libro_mayor import construir_libro_mayor
from ..dominio.numeros import es_cero, redondear
from ..dominio.tipos import Caso, Naturaleza

COLUMNAS_IMPORTACION = ["numero", "fecha", "glosa", "codigo", "debe", "haber"]

#: Nombres que se aceptan para cada columna al importar, en minúsculas.
ALIAS_COLUMNAS: Dict[str, Sequence[str]] = {
    "numero": ("numero", "n", "nro", "asiento", "numero de asiento"),
    "fecha": ("fecha", "dia", "date"),
    "glosa": ("glosa", "descripcion", "detalle", "concepto"),
    "codigo": ("codigo", "cuenta", "codigo de cuenta", "cod"),
    "debe": ("debe", "cargo", "debito"),
    "haber": ("haber", "abono", "credito"),
}


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def _decimal(valor) -> Decimal:
    texto = _texto(valor).replace(" ", "").replace(",", "")
    if not texto:
        return Decimal("0.00")
    try:
        return redondear(Decimal(texto))
    except (InvalidOperation, ValueError):
        raise ValueError("El importe " + texto + " no es un numero valido.")


def _num(valor: Decimal) -> float:
    """Decimal a float, solo para escribir en Excel (pandas no usa Decimal)."""
    return float(valor)


# ---------------------------------------------------------------- exportación


def tabla_libro_diario(caso: Caso) -> pd.DataFrame:
    diario = construir_libro_diario(caso)
    filas = []
    for item in diario.asientos:
        for fila in item.filas:
            filas.append(
                {
                    "N.": item.asiento.numero,
                    "Fecha": formatear_fecha(item.asiento.fecha),
                    "Glosa": item.asiento.glosa,
                    "Código": fila.cuenta.codigo if fila.cuenta else "",
                    "Cuenta": fila.cuenta.nombre if fila.cuenta else "",
                    "Debe": _num(fila.debe),
                    "Haber": _num(fila.haber),
                }
            )
    filas.append(
        {
            "N.": "",
            "Fecha": "",
            "Glosa": "TOTAL GENERAL",
            "Código": "",
            "Cuenta": "",
            "Debe": _num(diario.total_debe),
            "Haber": _num(diario.total_haber),
        }
    )
    return pd.DataFrame(filas)


def tabla_libro_mayor(caso: Caso) -> pd.DataFrame:
    mayor = construir_libro_mayor(caso)
    filas = []
    for grupo in mayor.grupos:
        for item in grupo.cuentas:
            for movimiento in item.movimientos:
                filas.append(
                    {
                        "Grupo": grupo.etiqueta,
                        "Código": item.cuenta.codigo,
                        "Cuenta": item.cuenta.nombre,
                        "Fecha": formatear_fecha(movimiento.fecha),
                        "N.": movimiento.numero,
                        "Glosa": movimiento.glosa,
                        "Debe": _num(movimiento.debe),
                        "Haber": _num(movimiento.haber),
                        "Saldo": _num(movimiento.saldo),
                    }
                )
            filas.append(
                {
                    "Grupo": grupo.etiqueta,
                    "Código": item.cuenta.codigo,
                    "Cuenta": item.cuenta.nombre,
                    "Fecha": "",
                    "N.": "",
                    "Glosa": "Saldo deudor"
                    if item.naturaleza_saldo == Naturaleza.DEUDOR
                    else "Saldo acreedor",
                    "Debe": _num(item.total_debe),
                    "Haber": _num(item.total_haber),
                    "Saldo": _num(item.saldo),
                }
            )
    return pd.DataFrame(filas)


def tabla_balance_comprobacion(caso: Caso) -> pd.DataFrame:
    balance = construir_balance_comprobacion(caso)
    filas = [
        {
            "Código": fila.cuenta.codigo,
            "Cuenta": fila.cuenta.nombre,
            "Suma Debe": _num(fila.suma_debe),
            "Suma Haber": _num(fila.suma_haber),
            "Saldo Deudor": _num(fila.saldo_deudor),
            "Saldo Acreedor": _num(fila.saldo_acreedor),
        }
        for fila in balance.filas
    ]
    filas.append(
        {
            "Código": "",
            "Cuenta": "TOTALES",
            "Suma Debe": _num(balance.total_debe),
            "Suma Haber": _num(balance.total_haber),
            "Saldo Deudor": _num(balance.total_deudor),
            "Saldo Acreedor": _num(balance.total_acreedor),
        }
    )
    return pd.DataFrame(filas)


def tabla_estado_resultados(caso: Caso) -> pd.DataFrame:
    estado = construir_estado_resultados(caso)
    filas = []
    for fila in estado.filas:
        if fila.clase == "detalle" and es_cero(fila.monto):
            continue
        filas.append(
            {
                "Concepto": ("(-) " if fila.signo == "-" else "") + fila.etiqueta,
                "Importe": _num(fila.monto),
                "Tipo de fila": fila.clase,
            }
        )
    return pd.DataFrame(filas)


def tabla_balance_general(caso: Caso) -> pd.DataFrame:
    general = construir_balance_general(caso)
    filas = []
    bloques = [
        general.activo_corriente,
        general.activo_no_corriente,
        general.pasivo_corriente,
        general.pasivo_no_corriente,
        general.patrimonio,
    ]
    for bloque in bloques:
        for detalle in bloque.cuentas:
            filas.append(
                {
                    "Bloque": bloque.etiqueta,
                    "Código": detalle.cuenta.codigo,
                    "Concepto": detalle.cuenta.nombre,
                    "Importe": _num(detalle.monto),
                }
            )
        if bloque.cuentas:
            filas.append(
                {
                    "Bloque": bloque.etiqueta,
                    "Código": "",
                    "Concepto": "Total " + bloque.etiqueta.lower(),
                    "Importe": _num(bloque.total),
                }
            )
    finales = [
        ("Resultado del ejercicio", general.resultado_ejercicio),
        ("TOTAL ACTIVO", general.total_activo),
        ("TOTAL PASIVO", general.total_pasivo),
        ("TOTAL PATRIMONIO", general.total_patrimonio),
        ("TOTAL PASIVO + PATRIMONIO", general.total_pasivo_patrimonio),
    ]
    for etiqueta, monto in finales:
        filas.append({"Bloque": "", "Código": "", "Concepto": etiqueta, "Importe": _num(monto)})
    return pd.DataFrame(filas)


def tabla_plan_cuentas(caso: Caso) -> pd.DataFrame:
    from ..dominio.cuentas import ETIQUETA_RUBRO, ETIQUETA_TIPO, ordenar_cuentas

    filas = [
        {
            "Código": cuenta.codigo,
            "Cuenta": cuenta.nombre,
            "Tipo": ETIQUETA_TIPO[cuenta.tipo],
            "Clasificación": ETIQUETA_RUBRO[cuenta.rubro] if cuenta.rubro else "",
        }
        for cuenta in ordenar_cuentas(caso.cuentas)
    ]
    return pd.DataFrame(filas)


HOJAS = [
    ("Plan de cuentas", tabla_plan_cuentas),
    ("Libro Diario", tabla_libro_diario),
    ("Libro Mayor", tabla_libro_mayor),
    ("Balance Comprobacion", tabla_balance_comprobacion),
    ("Estado Resultados", tabla_estado_resultados),
    ("Balance General", tabla_balance_general),
]


def exportar_excel(caso: Caso) -> bytes:
    """Un libro de Excel con una hoja por reporte."""
    destino = io.BytesIO()
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        for nombre_hoja, armar in HOJAS:
            tabla = armar(caso)
            if tabla.empty:
                tabla = pd.DataFrame([{"Aviso": "Sin datos para este reporte."}])
            tabla.to_excel(escritor, sheet_name=nombre_hoja, index=False)
            _ajustar_ancho(escritor.book[nombre_hoja], tabla)
    return destino.getvalue()


def _ajustar_ancho(hoja, tabla: pd.DataFrame):
    """Ancho de columna según el texto más largo, para que se lea sin tocar nada."""
    for indice, columna in enumerate(tabla.columns, start=1):
        largos = [len(str(columna))]
        largos.extend(len(str(valor)) for valor in tabla[columna].head(200))
        ancho = min(max(largos) + 2, 48)
        hoja.column_dimensions[hoja.cell(row=1, column=indice).column_letter].width = ancho


def nombre_excel(caso: Caso) -> str:
    from .pdf import nombre_reporte

    return nombre_reporte(caso).replace("reporte-financiero-", "reportes-").replace(".pdf", ".xlsx")


# ---------------------------------------------------------------- importación


def plantilla_importacion() -> bytes:
    """Hoja de ejemplo con las columnas que espera la importación."""
    ejemplo = pd.DataFrame(
        [
            {
                "numero": 1,
                "fecha": "01/01/2024",
                "glosa": "Aporte de capital",
                "codigo": "101",
                "debe": 50000,
                "haber": 0,
            },
            {
                "numero": 1,
                "fecha": "01/01/2024",
                "glosa": "Aporte de capital",
                "codigo": "501",
                "debe": 0,
                "haber": 50000,
            },
        ],
        columns=COLUMNAS_IMPORTACION,
    )
    destino = io.BytesIO()
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        ejemplo.to_excel(escritor, sheet_name="Asientos", index=False)
        _ajustar_ancho(escritor.book["Asientos"], ejemplo)
    return destino.getvalue()


def _normalizar_columnas(tabla: pd.DataFrame) -> pd.DataFrame:
    """Acepta Debe, DEBE, Cargo... y deja los nombres que usa el importador."""
    renombre = {}
    for columna in tabla.columns:
        limpio = _texto(columna).lower()
        for clave, alias in ALIAS_COLUMNAS.items():
            if limpio in alias:
                renombre[columna] = clave
                break
    tabla = tabla.rename(columns=renombre)
    faltan = [clave for clave in ("fecha", "codigo") if clave not in tabla.columns]
    if faltan:
        raise ValueError(
            "Al archivo le faltan columnas: " + ", ".join(faltan) + ". Usa la plantilla."
        )
    return tabla


def leer_asientos(archivo, nombre: str = "") -> List[dict]:
    """Lee el archivo y devuelve los asientos agrupados por número.

    Cada asiento es {"numero", "fecha", "glosa", "lineas": [{"codigo", "debe",
    "haber"}]}. Acepta .xlsx, .xls y .csv.
    """
    nombre = (nombre or getattr(archivo, "name", "") or "").lower()
    if nombre.endswith(".csv"):
        tabla = pd.read_csv(archivo, dtype=str, keep_default_na=False)
    else:
        tabla = pd.read_excel(archivo, dtype=str, keep_default_na=False)

    tabla = _normalizar_columnas(tabla)

    agrupados: Dict[str, dict] = {}
    orden: List[str] = []
    for posicion, registro in enumerate(tabla.to_dict("records"), start=2):
        codigo = _texto(registro.get("codigo"))
        debe = _decimal(registro.get("debe"))
        haber = _decimal(registro.get("haber"))
        if not codigo and es_cero(debe) and es_cero(haber):
            continue
        if not codigo:
            raise ValueError("Fila " + str(posicion) + ": falta el codigo de cuenta.")

        clave = _texto(registro.get("numero")) or "fila-" + str(posicion)
        if clave not in agrupados:
            orden.append(clave)
            agrupados[clave] = {
                "numero": clave,
                "fecha": _fecha(registro.get("fecha"), posicion),
                "glosa": _texto(registro.get("glosa")),
                "lineas": [],
            }
        asiento = agrupados[clave]
        if not asiento["glosa"]:
            asiento["glosa"] = _texto(registro.get("glosa"))
        asiento["lineas"].append({"codigo": codigo, "debe": debe, "haber": haber})

    if not orden:
        raise ValueError("El archivo no tiene asientos para importar.")
    return [agrupados[clave] for clave in orden]


def _fecha(valor, posicion: int):
    """Acepta 01/01/2024, 2024-01-01 y las fechas propias de Excel."""
    texto = _texto(valor)
    if not texto:
        raise ValueError("Fila " + str(posicion) + ": falta la fecha.")
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(texto, format=formato).date()
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(texto, dayfirst=True).date()
    except (ValueError, TypeError):
        raise ValueError(
            "Fila " + str(posicion) + ": la fecha " + texto + " no se entiende. Usa dd/mm/aaaa."
        )
