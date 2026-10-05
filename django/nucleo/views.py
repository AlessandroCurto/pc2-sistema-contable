"""Vistas: una por pantalla, más las acciones de descarga e importación.

Las vistas no calculan nada contable: piden el caso con a_dominio() y llaman
al motor (nucleo/dominio). Así la pantalla solo acomoda lo que el motor ya
calculó, igual que los componentes de la versión en React.
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .datos.casos_demo import crear_caso_demo, obtener_plantilla_caso
from .datos.plantillas_cuentas import obtener_plantilla
from .dominio.asientos import ordenar_asientos, resumir_asiento, siguiente_numero
from .dominio.balance_comprobacion import construir_balance_comprobacion
from .dominio.balance_general import construir_balance_general
from .dominio.cuentas import ETIQUETA_TIPO, ordenar_cuentas
from .dominio.estado_resultados import construir_estado_resultados
from .dominio.libro_diario import FiltroDiario, construir_libro_diario
from .dominio.libro_mayor import construir_libro_mayor
from .forms import (
    AsientoForm,
    CasoForm,
    CasoNuevoForm,
    CuentaForm,
    FiltroDiarioForm,
    ImportarAsientosForm,
    ImportarCasoForm,
    LineaFormSetFactory,
    ReporteForm,
    SeleccionDemoForm,
)
from .models import Asiento, Caso, Cuenta
from .navegacion import accesos_rapidos
from .servicios import excel as servicio_excel
from .servicios.casos import (
    exportar_json,
    importar_asientos,
    importar_json,
    nombre_respaldo,
)
from .servicios.pdf import SECCIONES, generar_reporte_pdf, nombre_reporte
from .sesion import abrir_caso, caso_activo, cerrar_caso

SIN_CASO = "Primero abre un caso en la pantalla de Casos."


def _exige_caso(request):
    """Devuelve el caso abierto, o None si hay que mandar a Casos."""
    caso = caso_activo(request)
    if caso is None:
        messages.info(request, SIN_CASO)
    return caso


# ------------------------------------------------------------------- inicio


def inicio(request):
    caso = caso_activo(request)
    if caso is None:
        return render(request, "nucleo/inicio.html", {"casos": Caso.objects.all()})

    dominio = caso.a_dominio()
    balance = construir_balance_comprobacion(dominio)
    estado = construir_estado_resultados(dominio)
    general = construir_balance_general(dominio)
    ultimos = list(reversed(ordenar_asientos(dominio.asientos)[-5:]))

    return render(
        request,
        "nucleo/inicio.html",
        {
            "casos": Caso.objects.all(),
            "caso": caso,
            "dominio": dominio,
            "balance": balance,
            "estado": estado,
            "general": general,
            "ultimos": [
                {"asiento": asiento, "resumen": resumir_asiento(asiento.lineas)}
                for asiento in ultimos
            ],
            "accesos": accesos_rapidos(),
            "total_cuentas": len(dominio.cuentas),
            "total_asientos": len(dominio.asientos),
        },
    )


# -------------------------------------------------------------------- casos


def casos(request):
    formulario = CasoNuevoForm()
    formulario_demo = SeleccionDemoForm()
    formulario_importar = ImportarCasoForm()

    if request.method == "POST" and request.POST.get("accion") == "nuevo":
        formulario = CasoNuevoForm(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                caso = formulario.save()
                plantilla = obtener_plantilla(formulario.cleaned_data["plantilla_cuentas"])
                Cuenta.objects.bulk_create(
                    [
                        Cuenta(
                            caso=caso,
                            codigo=definicion.codigo,
                            nombre=definicion.nombre,
                            tipo=definicion.tipo,
                            rubro=definicion.rubro or "",
                        )
                        for definicion in plantilla.cuentas
                    ]
                )
            abrir_caso(request, caso)
            messages.success(request, "Caso creado y abierto: " + caso.nombre + ".")
            return redirect("inicio")

    return render(
        request,
        "nucleo/casos.html",
        {
            "formulario": formulario,
            "formulario_demo": formulario_demo,
            "formulario_importar": formulario_importar,
            "lista": Caso.objects.all(),
        },
    )


@require_POST
def caso_abrir(request, pk: int):
    caso = get_object_or_404(Caso, pk=pk)
    abrir_caso(request, caso)
    messages.success(request, "Caso abierto: " + caso.nombre + ".")
    return redirect("inicio")


@require_POST
def caso_eliminar(request, pk: int):
    caso = get_object_or_404(Caso, pk=pk)
    nombre = caso.nombre
    caso.delete()
    cerrar_caso(request)
    messages.success(request, "Caso eliminado: " + nombre + ".")
    return redirect("casos")


@require_POST
def caso_demo(request):
    formulario = SeleccionDemoForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, "Elige un caso de ejemplo.")
        return redirect("casos")
    plantilla = obtener_plantilla_caso(formulario.cleaned_data["plantilla"])
    caso = crear_caso_demo(plantilla)
    abrir_caso(request, caso)
    messages.success(request, "Caso de ejemplo cargado: " + caso.nombre + ".")
    return redirect("inicio")


def caso_exportar(request, pk: int):
    caso = get_object_or_404(Caso, pk=pk)
    respuesta = JsonResponse(exportar_json(caso), json_dumps_params={"ensure_ascii": False, "indent": 2})
    respuesta["Content-Disposition"] = 'attachment; filename="' + nombre_respaldo(caso) + '"'
    return respuesta


@require_POST
def caso_importar(request):
    formulario = ImportarCasoForm(request.POST, request.FILES)
    if not formulario.is_valid():
        messages.error(request, "Elige el archivo JSON del caso.")
        return redirect("casos")
    try:
        datos = json.load(formulario.cleaned_data["archivo"])
        caso = importar_json(datos)
    except (ValueError, UnicodeDecodeError) as error:
        messages.error(request, "No se pudo importar: " + str(error))
        return redirect("casos")
    abrir_caso(request, caso)
    messages.success(request, "Caso importado y abierto: " + caso.nombre + ".")
    return redirect("inicio")


# ----------------------------------------------------------- plan de cuentas


def plan_cuentas(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")

    formulario = CuentaForm(caso=caso)
    if request.method == "POST":
        formulario = CuentaForm(request.POST, caso=caso)
        if formulario.is_valid():
            cuenta = formulario.save(commit=False)
            cuenta.caso = caso
            cuenta.save()
            messages.success(request, "Cuenta agregada: " + str(cuenta) + ".")
            return redirect("plan_cuentas")

    cuentas = list(caso.cuentas.all())
    orden = {str(cuenta.id): indice for indice, cuenta in enumerate(ordenar_cuentas([c.a_dominio() for c in cuentas]))}
    cuentas.sort(key=lambda cuenta: orden.get(str(cuenta.pk), 0))

    return render(
        request,
        "nucleo/plan_cuentas.html",
        {"caso": caso, "cuentas": cuentas, "formulario": formulario},
    )


def cuenta_editar(request, pk: int):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    cuenta = get_object_or_404(Cuenta, pk=pk, caso=caso)
    formulario = CuentaForm(instance=cuenta, caso=caso)
    if request.method == "POST":
        formulario = CuentaForm(request.POST, instance=cuenta, caso=caso)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "Cuenta actualizada: " + str(cuenta) + ".")
            return redirect("plan_cuentas")
    return render(
        request,
        "nucleo/cuenta_form.html",
        {"caso": caso, "cuenta": cuenta, "formulario": formulario},
    )


@require_POST
def cuenta_eliminar(request, pk: int):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    cuenta = get_object_or_404(Cuenta, pk=pk, caso=caso)
    if cuenta.tiene_movimientos:
        messages.error(
            request,
            "No se puede eliminar " + str(cuenta) + ": tiene asientos registrados.",
        )
    else:
        nombre = str(cuenta)
        cuenta.delete()
        messages.success(request, "Cuenta eliminada: " + nombre + ".")
    return redirect("plan_cuentas")


# -------------------------------------------------------------- asientos


def registrar_asiento(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    if not caso.cuentas.exists():
        messages.info(request, "Agrega cuentas al plan antes de registrar asientos.")
        return redirect("plan_cuentas")

    numero = siguiente_numero([asiento.a_dominio() for asiento in caso.asientos.all()])

    if request.method == "POST":
        formulario = AsientoForm(request.POST)
        formset = LineaFormSetFactory(
            request.POST, caso=caso, formulario_asiento=formulario, instance=Asiento(caso=caso)
        )
        if formulario.is_valid() and formset.is_valid():
            with transaction.atomic():
                asiento = formulario.save(commit=False)
                asiento.caso = caso
                asiento.numero = numero
                asiento.save()
                formset.instance = asiento
                lineas = formset.save(commit=False)
                orden = 0
                for linea in lineas:
                    if linea.cuenta_id is None:
                        continue
                    linea.asiento = asiento
                    linea.orden = orden
                    linea.save()
                    orden += 1
                for borrada in formset.deleted_objects:
                    borrada.delete()
            messages.success(request, "Asiento " + str(asiento.numero) + " registrado.")
            return redirect("libro_diario")
    else:
        formulario = AsientoForm()
        formset = LineaFormSetFactory(caso=caso, instance=Asiento(caso=caso))

    return render(
        request,
        "nucleo/registrar_asiento.html",
        {
            "caso": caso,
            "formulario": formulario,
            "formset": formset,
            "numero": numero,
            "formulario_importar": ImportarAsientosForm(),
        },
    )


@require_POST
def asiento_eliminar(request, pk: int):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    asiento = get_object_or_404(Asiento, pk=pk, caso=caso)
    numero = asiento.numero
    asiento.delete()
    messages.success(request, "Asiento " + str(numero) + " eliminado.")
    return redirect("libro_diario")


@require_POST
def asientos_importar(request):
    """Importa asientos de un Excel o CSV. pandas lee, el motor valida."""
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    formulario = ImportarAsientosForm(request.POST, request.FILES)
    if not formulario.is_valid():
        messages.error(request, "Elige un archivo .xlsx o .csv.")
        return redirect("registrar_asiento")

    archivo = formulario.cleaned_data["archivo"]
    try:
        leidos = servicio_excel.leer_asientos(archivo, archivo.name)
    except (ValueError, KeyError) as error:
        messages.error(request, "No se pudo leer el archivo: " + str(error))
        return redirect("registrar_asiento")

    resultado = importar_asientos(
        caso, leidos, crear_cuentas=formulario.cleaned_data["crear_cuentas"]
    )
    if resultado.importados:
        messages.success(request, "Asientos importados: " + str(resultado.importados) + ".")
    for motivo in resultado.errores:
        messages.error(request, motivo)
    return redirect("libro_diario" if resultado.importados else "registrar_asiento")


def plantilla_asientos(request):
    contenido = servicio_excel.plantilla_importacion()
    respuesta = HttpResponse(
        contenido,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="plantilla-asientos.xlsx"'
    return respuesta


# -------------------------------------------------------------- reportes


def libro_diario(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    formulario = FiltroDiarioForm(request.GET or None, caso=caso)
    filtro = FiltroDiario()
    if formulario.is_valid():
        cuenta = formulario.cleaned_data.get("cuenta")
        filtro = FiltroDiario(
            desde=formulario.cleaned_data.get("desde"),
            hasta=formulario.cleaned_data.get("hasta"),
            cuenta_id=str(cuenta.pk) if cuenta else "",
            texto=formulario.cleaned_data.get("texto") or "",
        )
    dominio = caso.a_dominio()
    return render(
        request,
        "nucleo/libro_diario.html",
        {
            "caso": caso,
            "formulario": formulario,
            "diario": construir_libro_diario(dominio, filtro),
            "filtrado": not filtro.vacio(),
            "total_asientos": len(dominio.asientos),
        },
    )


def libro_mayor(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    return render(
        request,
        "nucleo/libro_mayor.html",
        {"caso": caso, "mayor": construir_libro_mayor(caso.a_dominio())},
    )


def balance_comprobacion(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    return render(
        request,
        "nucleo/balance_comprobacion.html",
        {"caso": caso, "balance": construir_balance_comprobacion(caso.a_dominio())},
    )


def estado_resultados(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    dominio = caso.a_dominio()
    return render(
        request,
        "nucleo/estado_resultados.html",
        {
            "caso": caso,
            "estado": construir_estado_resultados(dominio),
            "simbolo": dominio.empresa.simbolo_moneda,
        },
    )


def balance_general(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    dominio = caso.a_dominio()
    general = construir_balance_general(dominio)
    return render(
        request,
        "nucleo/balance_general.html",
        {
            "caso": caso,
            "general": general,
            "bloques_activo": [general.activo_corriente, general.activo_no_corriente],
            "bloques_pasivo": [general.pasivo_corriente, general.pasivo_no_corriente],
            "simbolo": dominio.empresa.simbolo_moneda,
        },
    )


# -------------------------------------------------------------- descargas


def reporte(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")

    formulario = ReporteForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        dominio = caso.a_dominio()
        try:
            contenido = generar_reporte_pdf(
                dominio,
                formulario.cleaned_data["secciones"],
                formulario.cleaned_data.get("nombre_empresa", ""),
            )
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("reporte")
        respuesta = HttpResponse(contenido, content_type="application/pdf")
        respuesta["Content-Disposition"] = (
            'attachment; filename="' + nombre_reporte(dominio) + '"'
        )
        return respuesta

    return render(
        request,
        "nucleo/reporte.html",
        {
            "caso": caso,
            "formulario": formulario,
            "secciones": SECCIONES,
            "url_excel": reverse("reporte_excel"),
        },
    )


def reporte_excel(request):
    """Los cinco reportes en un Excel, una hoja por reporte (pandas)."""
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    dominio = caso.a_dominio()
    respuesta = HttpResponse(
        servicio_excel.exportar_excel(dominio),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="' + servicio_excel.nombre_excel(dominio) + '"'
    )
    return respuesta


# ----------------------------------------------------------- configuración


def configuracion(request):
    caso = _exige_caso(request)
    if caso is None:
        return redirect("casos")
    formulario = CasoForm(instance=caso)
    if request.method == "POST":
        formulario = CasoForm(request.POST, instance=caso)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "Configuración guardada.")
            return redirect("configuracion")
    return render(
        request,
        "nucleo/configuracion.html",
        {"caso": caso, "formulario": formulario, "etiquetas_tipo": ETIQUETA_TIPO},
    )
