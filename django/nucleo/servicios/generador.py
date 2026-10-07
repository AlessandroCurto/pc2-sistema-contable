"""Inventa un caso contable nuevo, coherente y con solución.

No escribe los asientos: escribe el **enunciado**, y después lo pasa por el
mismo lector que usa el chat (`servicios/enunciados.py`). Si de ahí no salen
ocho asientos cuadrados y con utilidad positiva, el enunciado se descarta y se
genera otro. Así lo que se entrega siempre se puede resolver, y se resuelve con
el código que ya está probado, no con una copia aparte.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.estado_resultados import construir_estado_resultados
from . import enunciados

IGV = Decimal("1.18")

PREFIJOS = ("Comercial", "Distribuidora", "Importadora", "Corporación", "Negocios",
            "Inversiones", "Grupo", "Representaciones", "Almacenes", "Multiservicios")
NOMBRES = ("Andina", "del Pacífico", "San Martín", "Los Robles", "Huascarán", "El Sol",
           "Primavera", "Santa Rosa", "Pacasmayo", "Vista Alegre", "Los Olivos", "Tahuantinsuyo")
FORMAS = ("S.A.C.", "S.R.L.", "E.I.R.L.")

PROVEEDORES = ("Importaciones del Norte S.A.", "Textiles Andinos S.A.C.", "Aceros del Centro S.A.",
               "Distribuidora Mayorista S.A.C.", "Insumos Industriales S.A.",
               "Comercializadora Oriente S.A.C.")
CLIENTES = ("Constructora Huaraz E.I.R.L.", "Ferretería La Unión S.R.L.",
            "Minimarket El Ahorro E.I.R.L.", "Servicios Generales Lima S.A.C.",
            "Bodegas Unidas S.R.L.", "Transportes del Sur E.I.R.L.")

MESES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
         7: "julio", 8: "agosto", 9: "setiembre", 10: "octubre", 11: "noviembre",
         12: "diciembre"}

GASTOS = (
    ("arriendo", "Pago del arriendo mensual del local con cheque"),
    ("personal", "Pago de los sueldos del mes con cheque"),
)


@dataclass
class CasoGenerado:
    enunciado: str
    empresa: str
    asientos: int
    total_debe: Decimal
    utilidad_neta: Decimal


def _miles(azar: random.Random, desde: int, hasta: int, paso: int = 100) -> Decimal:
    """Un importe redondo: los enunciados de clase no usan céntimos."""
    return Decimal(azar.randrange(desde, hasta + 1, paso) * 1000)


def _texto(azar: random.Random) -> str:
    """Arma un enunciado con ocho operaciones encadenadas."""
    empresa = f"{azar.choice(PREFIJOS)} {azar.choice(NOMBRES)} {azar.choice(FORMAS)}"
    proveedor = azar.choice(PROVEEDORES)
    cliente = azar.choice(CLIENTES)
    anio = azar.choice((2024, 2025))
    mes = azar.randrange(1, 13)
    ultimo = (date(anio + (mes == 12), mes % 12 + 1, 1) - date.resolution).day
    f = lambda dia: f"{dia:02d}/{mes:02d}/{anio}"
    # "1 letras" se lee mal; y si la frase termina en el nombre, su propio
    # punto cierra la oración y no hay que agregar otro.
    letra = lambda n: "1 letra" if n == 1 else f"{n} letras"
    derivada = lambda n: "derivada" if n == 1 else "derivadas"
    cierra = lambda nombre: nombre if nombre.endswith(".") else nombre + "."

    # --- inventario inicial: el activo tiene que igualar al pasivo más capital
    efectivo = _miles(azar, 800, 2500)
    banco = _miles(azar, 1500, 3500)
    clientes = _miles(azar, 200, 800)
    mercaderias = _miles(azar, 300, 900)
    proveedores = _miles(azar, 400, 900)
    capital = efectivo + banco + clientes + mercaderias - proveedores

    # --- compra con letras: el total se reparte en cuotas iguales
    letras_compra = azar.choice((4, 5, 6, 8, 10))
    compra = Decimal(azar.randrange(40, 160) * 10000 * letras_compra // 10)
    compra = (compra // letras_compra) * letras_compra          # divisible, sin céntimos
    base_compra = (compra / IGV).quantize(Decimal("0.01"))

    # --- venta: una parte al contado y el resto en letras
    letras_venta = azar.choice((2, 4, 5))
    venta = _miles(azar, 300, 900, 50)
    porcentaje = azar.choice((30, 40, 50, 60))

    # --- gastos y pagos
    papel_gasto, glosa_gasto = azar.choice(GASTOS)
    gasto = _miles(azar, 60, 200, 10)
    porcentaje_deuda = azar.choice((40, 50, 60, 75))
    cobradas = azar.randrange(1, letras_venta)
    pagadas = azar.randrange(1, letras_compra)

    # --- existencia final: deja un costo de ventas que no se coma la utilidad
    disponible = mercaderias + base_compra
    costo_objetivo = (venta * Decimal(azar.randrange(35, 56)) / 100).quantize(Decimal("1"))
    final = (disponible - costo_objetivo).quantize(Decimal("1"))

    lineas = [
        f"La empresa {empresa} presenta el siguiente inventario inicial al 01 de "
        f"{MESES[mes]} del {anio}: dinero en efectivo S/ {efectivo:,.0f}, cuenta corriente "
        f"S/ {banco:,.0f}, Clientes S/ {clientes:,.0f}, Mercaderías S/ {mercaderias:,.0f}, "
        f"Proveedores S/ {proveedores:,.0f} y capital S/ {capital:,.0f}.",

        f"{f(1)} - Compra de Mercadería: Se compran mercaderías a {proveedor} por un total "
        f"de S/ {compra:,.2f} (IGV incluido). El pago se fracciona firmando "
        f"{letra(letras_compra)} de cambio de igual valor.",

        f"{f(4)} - Venta de Mercadería: Se venden mercaderías a {cliente} por un valor neto "
        f"de S/ {venta:,.2f} (más IGV). El cliente cancela el {porcentaje}% del monto total "
        f"facturado en efectivo y por el saldo acepta {letra(letras_venta)} de cambio.",

        f"{f(10)} - Gasto Operativo: {glosa_gasto} por S/ {gasto:,.2f}.",

        f"{f(15)} - Amortización de Deuda: Se cancela el {porcentaje_deuda}% de la deuda "
        f"histórica (inventario inicial) que se mantenía con los proveedores, emitiendo "
        f"un cheque.",

        f"{f(20)} - Cobranza a Clientes: El cliente {cliente} cancela con cheque "
        f"{letra(cobradas)} {derivada(cobradas)} de la venta del {f(4)}.",

        f"{f(25)} - Pago de Letras: La empresa cancela con cheque {pagadas} de las letras "
        f"pendientes a favor del proveedor {cierra(proveedor)}",

        f"{f(ultimo)} - Ajuste por Costo de Ventas: Al cierre del mes, el conteo físico "
        f"determina una existencia final de mercaderías valorizada en S/ {final:,.2f}.",
    ]
    return "\n".join(lineas)


def generar(semilla: Optional[int] = None, intentos: int = 40) -> Optional[CasoGenerado]:
    """Un caso nuevo que el lector resuelve entero y deja con utilidad.

    Se comprueba antes de entregarlo: ocho asientos, ninguno descuadrado, el
    balance de comprobación cerrado y un resultado positivo. Si no sale, se
    intenta con otro.
    """
    azar = random.Random(semilla)
    for _ in range(intentos):
        texto = _texto(azar)
        lectura = enunciados.leer(texto, enunciados.CASO_VACIO)
        if lectura.problemas or len(lectura.asientos) != 8:
            continue
        if not all(asiento.cuadra for asiento in lectura.asientos):
            continue

        caso = _como_caso(texto, lectura)
        balance = construir_balance_comprobacion(caso)
        estado = construir_estado_resultados(caso)
        if not balance.cuadrado or estado.resultado_antes_impuesto <= 0:
            continue
        return CasoGenerado(
            enunciado=texto,
            empresa=enunciados.datos_del_caso(texto)["nombre"],
            asientos=len(lectura.asientos),
            total_debe=balance.total_debe,
            utilidad_neta=estado.utilidad_neta,
        )
    return None


def _como_caso(texto: str, lectura) -> "enunciados.CasoDominio":
    """Monta un caso en memoria para poder calcularle los reportes."""
    from ..dominio import tipos

    datos = enunciados.datos_del_caso(texto)
    cuentas = {linea.cuenta.codigo: linea.cuenta
               for asiento in lectura.asientos for linea in asiento.lineas}
    asientos: List[tipos.Asiento] = []
    for numero, propuesto in enumerate(lectura.asientos, start=1):
        asientos.append(tipos.Asiento(
            id=str(numero),
            numero=numero,
            fecha=propuesto.fecha or datos["periodo_inicio"] or date.today(),
            glosa=propuesto.glosa,
            lineas=[
                tipos.LineaAsiento(id=f"{numero}-{i}", cuenta_id=linea.cuenta.id,
                                   debe=linea.debe, haber=linea.haber)
                for i, linea in enumerate(propuesto.lineas)
            ],
        ))
    return tipos.Caso(
        id="generado",
        nombre=datos["nombre"],
        empresa=tipos.Empresa(
            nombre=datos["nombre"],
            simbolo_moneda="S/",
            periodo_inicio=datos["periodo_inicio"],
            periodo_fin=datos["periodo_fin"],
            tasa_impuesto_renta=datos["tasa_impuesto_renta"],
            impuesto_afecta_patrimonio=True,
        ),
        cuentas=list(cuentas.values()),
        asientos=asientos,
    )
