"""Direcciones. Los nombres coinciden con navegacion.py (el menu usa {% url %})."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("casos/", views.casos, name="casos"),
    path("casos/<int:pk>/abrir/", views.caso_abrir, name="caso_abrir"),
    path("casos/<int:pk>/eliminar/", views.caso_eliminar, name="caso_eliminar"),
    path("casos/<int:pk>/exportar/", views.caso_exportar, name="caso_exportar"),
    path("casos/demo/", views.caso_demo, name="caso_demo"),
    path("casos/importar/", views.caso_importar, name="caso_importar"),
    path("plan-de-cuentas/", views.plan_cuentas, name="plan_cuentas"),
    path("plan-de-cuentas/<int:pk>/editar/", views.cuenta_editar, name="cuenta_editar"),
    path("plan-de-cuentas/<int:pk>/eliminar/", views.cuenta_eliminar, name="cuenta_eliminar"),
    path("asientos/", views.registrar_asiento, name="registrar_asiento"),
    path("asientos/<int:pk>/eliminar/", views.asiento_eliminar, name="asiento_eliminar"),
    path("asientos/importar/", views.asientos_importar, name="asientos_importar"),
    path("asientos/plantilla/", views.plantilla_asientos, name="plantilla_asientos"),
    path("libro-diario/", views.libro_diario, name="libro_diario"),
    path("libro-mayor/", views.libro_mayor, name="libro_mayor"),
    path("balance-comprobacion/", views.balance_comprobacion, name="balance_comprobacion"),
    path("estado-resultados/", views.estado_resultados, name="estado_resultados"),
    path("balance-general/", views.balance_general, name="balance_general"),
    path("reporte/", views.reporte, name="reporte"),
    path("reporte/excel/", views.reporte_excel, name="reporte_excel"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("chatbot/", views.chatbot, name="chatbot"),
    path("asistente/registrar/", views.asistente_registrar, name="asistente_registrar"),
]
