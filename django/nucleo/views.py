"""Vistas: una por pantalla, más las acciones de descarga e importación.

Las vistas no calculan nada contable: piden el caso con a_dominio() y llaman
al motor (nucleo/dominio). Así la pantalla solo acomoda lo que el motor ya
calculó, igual que los componentes de la versión en React.
"""

from __future__ import annotations

import json
import os
import time

from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
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
from .models import Asiento, Caso, Cuenta, UsoAsistente
from .navegacion import accesos_rapidos
from .servicios import asistente
from .servicios import enunciados
from .servicios import generador
from .servicios import chatbot as chatbot_servicio
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


# ----------------------------------------------------------------- asistente

#: Tope por sesión y por hora. El sitio es público y cada pregunta cuesta.
CHAT_TOPE = 40

#: Tope de TODO el sitio por día, para las consultas que llegan a la API.
#: Se supera y el asistente sigue respondiendo, pero solo con lo local (gratis).
CHAT_TOPE_DIARIO = int(os.environ.get("CHATBOT_TOPE_DIARIO", "150"))
CHAT_VENTANA = 3600
CHAT_MAX_CARACTERES = 4000
CHAT_MAX_MENSAJES = 20


def _limite_alcanzado(request) -> bool:
    """Cuenta las preguntas de esta sesión dentro de la ventana de una hora."""
    ahora = time.time()
    inicio = request.session.get("chat_ventana", 0)
    usos = request.session.get("chat_usos", 0)
    if ahora - inicio > CHAT_VENTANA:
        inicio, usos = ahora, 0
    if usos >= CHAT_TOPE:
        return True
    request.session["chat_ventana"] = inicio
    request.session["chat_usos"] = usos + 1
    return False


def _queda_cupo_del_dia() -> bool:
    """Reserva un lugar del cupo diario. False si ya se agotó."""
    if CHAT_TOPE_DIARIO <= 0:
        return False
    hoy = timezone.localdate()
    uso, _ = UsoAsistente.objects.get_or_create(fecha=hoy)
    # Un UPDATE condicional: dos pedidos a la vez no pueden pasarse del tope.
    reservado = UsoAsistente.objects.filter(
        pk=uso.pk, consultas__lt=CHAT_TOPE_DIARIO
    ).update(consultas=F("consultas") + 1)
    return bool(reservado)


def _mensajes_validos(crudos):
    """Deja solo lo que la API acepta: roles correctos y texto no vacío."""
    if not isinstance(crudos, list) or not crudos:
        return None
    limpios = []
    for item in crudos[-CHAT_MAX_MENSAJES:]:
        if not isinstance(item, dict):
            return None
        rol = item.get("role")
        texto = item.get("content")
        if rol not in ("user", "assistant") or not isinstance(texto, str):
            return None
        texto = texto.strip()[:CHAT_MAX_CARACTERES]
        if texto:
            limpios.append({"role": rol, "content": texto})
    # La API exige que el primero y el último sean del usuario.
    while limpios and limpios[0]["role"] != "user":
        limpios.pop(0)
    if not limpios or limpios[-1]["role"] != "user":
        return None
    return limpios


def _elegir_caso(texto: str):
    """El caso guardado cuyo nombre más se parece a lo que pidió."""
    objetivo = asistente.normalizar(texto).strip()
    if not objetivo:
        return None
    palabras = set(objetivo.split())
    mejor, puntos = None, 0.0
    for caso in Caso.objects.all():
        for etiqueta in (caso.nombre, caso.razon_social):
            limpia = asistente.normalizar(etiqueta or "").strip()
            if not limpia:
                continue
            if limpia == objetivo:
                return caso
            propio = set(limpia.split())
            compartidas = palabras & propio
            if not compartidas:
                continue
            # Proporción de lo que pidió que aparece en el nombre del caso.
            puntaje = len(compartidas) / len(palabras)
            if objetivo in limpia or limpia in objetivo:
                puntaje += 1
            if puntaje > puntos:
                mejor, puntos = caso, puntaje
    return mejor if puntos >= 0.5 else None


def _evento(**datos) -> str:
    return "data: " + json.dumps(datos, ensure_ascii=False) + "\n\n"


@require_POST
def chatbot(request):
    """Responde en vivo: cada pedazo de texto sale apenas el modelo lo produce."""
    try:
        cuerpo = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "No se pudo leer la pregunta."}, status=400)

    mensajes = _mensajes_validos(cuerpo.get("mensajes"))
    if mensajes is None:
        return JsonResponse({"error": "La conversación llegó incompleta."}, status=400)

    if _limite_alcanzado(request):
        return JsonResponse(
            {"error": "Llegaste al límite de preguntas por hora. Vuelve a intentarlo más tarde."},
            status=429,
        )

    pregunta = mensajes[-1]["content"]

    # "genérame un caso": se inventa uno y se ofrece registrarlo.
    if asistente.pide_caso_nuevo(pregunta):
        generado = generador.generar()
        if generado is None:
            return _respuesta_en_vivo([
                _evento(t="No logré armar un caso coherente ahora. Inténtalo de nuevo."),
                _evento(fin=True),
            ])
        lectura = enunciados.leer(generado.enunciado, enunciados.CASO_VACIO)
        texto = (
            f"Te armé un caso nuevo: **{generado.empresa}**, con {generado.asientos} "
            f"operaciones.\n\nLo comprobé antes de dártelo: los asientos cuadran, el "
            f"balance de comprobación cierra en **S/ {generado.total_debe:,.2f}** y el "
            f"período deja una utilidad neta de **S/ {generado.utilidad_neta:,.2f}**.\n\n"
            "### Enunciado\n\n```\n" + generado.enunciado + "\n```\n\n"
            + enunciados.a_markdown(lectura, enunciados.CASO_VACIO)
        )
        return _respuesta_en_vivo([
            _evento(t=texto),
            _evento(accion="registrar", texto=generado.enunciado),
        ])

    # "abre el caso X": se cambia de caso y se le pide a la pantalla recargar.
    pedido = asistente.caso_pedido(pregunta)
    if pedido:
        elegido = _elegir_caso(pedido)
        if elegido is not None:
            abrir_caso(request, elegido)
            texto = (
                f"Listo, abrí **{elegido.nombre}** "
                f"({elegido.cuentas.count()} cuentas, {elegido.asientos.count()} asientos). "
                "Recargo la pantalla para que lo veas."
            )
            return _respuesta_en_vivo([_evento(t=texto), _evento(accion="recargar")])
        nombres = list(Caso.objects.values_list("nombre", flat=True))
        if nombres:
            disponibles = "Tienes guardados:\n\n" + "\n".join("- " + n for n in nombres)
        else:
            disponibles = "No tienes ningún caso guardado todavía."
        texto = f"No encontré ningún caso que se llame «{pedido}».\n\n{disponibles}"
        return _respuesta_en_vivo([_evento(t=texto), _evento(fin=True)])

    caso = caso_activo(request)
    dominio = caso.a_dominio() if caso is not None else None

    # La API solo entra si está configurada y si al sitio le queda cupo hoy.
    permitir_api = (
        chatbot_servicio.hay_api()
        and not asistente.fue_entendida(pregunta)
        and _queda_cupo_del_dia()
    )

    ofrecer_registro = asistente.hay_enunciado(pregunta, dominio)

    def flujo():
        try:
            for pedazo in chatbot_servicio.responder_en_vivo(
                mensajes, dominio, permitir_api=permitir_api
            ):
                yield _evento(t=pedazo)
            if ofrecer_registro:
                yield _evento(accion="registrar", texto=pregunta)
        except chatbot_servicio.ChatbotNoConfigurado as error:
            yield _evento(error=str(error))
        except Exception:
            yield _evento(
                error="El asistente no está disponible en este momento. Inténtalo de nuevo."
            )
        yield _evento(fin=True)

    return _respuesta_en_vivo(flujo())


def _respuesta_en_vivo(trozos) -> StreamingHttpResponse:
    respuesta = StreamingHttpResponse(trozos, content_type="text/event-stream")
    respuesta["Cache-Control"] = "no-cache"
    respuesta["X-Accel-Buffering"] = "no"  # que el proxy de Render no lo retenga
    return respuesta


class _SinAsientos(Exception):
    """Corta la transacción para no dejar un caso vacío a medio crear."""


@require_POST
def asistente_registrar(request):
    """Guarda en el caso los asientos que el asistente leyó de un enunciado.

    Si no hay caso abierto lo crea con los datos del propio enunciado, y si al
    plan de cuentas le faltan cuentas las agrega: así el estudiante solo tiene
    que pegar el texto.
    """
    try:
        texto = json.loads(request.body.decode("utf-8")).get("texto", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "No se pudo leer el enunciado."}, status=400)
    if not isinstance(texto, str) or not texto.strip():
        return JsonResponse({"error": "No se pudo leer el enunciado."}, status=400)
    texto = texto[:CHAT_MAX_CARACTERES]

    caso = caso_activo(request)
    # Las operaciones de otra empresa no van dentro del caso abierto.
    creado = enunciados.nombra_otra_empresa(texto, caso.a_dominio() if caso else None)
    try:
        with transaction.atomic():
            if creado:
                caso = Caso.objects.create(**enunciados.datos_del_caso(texto))

            lectura = enunciados.leer(texto, caso.a_dominio())
            if not lectura.asientos:
                raise _SinAsientos()

            # Se cuentan antes de crearlas: después ya no son nuevas.
            agregadas = len(lectura.cuentas_nuevas)
            for nueva in lectura.cuentas_nuevas:
                Cuenta.objects.get_or_create(
                    caso=caso,
                    codigo=nueva.codigo,
                    defaults={
                        "nombre": nueva.nombre,
                        "tipo": nueva.tipo.value,
                        "rubro": nueva.rubro.value if nueva.rubro else "",
                    },
                )

            # Se relee con el plan ya completo: ahora las cuentas son reales.
            dominio = caso.a_dominio()
            lectura = enunciados.leer(texto, dominio)
            resultado = importar_asientos(caso, enunciados.a_importables(lectura, dominio))
    except _SinAsientos:
        return JsonResponse({"error": "Ya no reconozco asientos en ese texto."}, status=400)

    if creado:
        abrir_caso(request, caso)
    return JsonResponse({
        "guardados": resultado.importados,
        "errores": resultado.errores,
        "cuentas": agregadas,
        "caso": caso.nombre if creado else "",
        "url": reverse("libro_diario"),
    })
