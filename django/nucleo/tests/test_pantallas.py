"""Pruebas de las pantallas: que abran, que guarden y que descarguen bien."""

import io
import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from ..datos.casos_demo import CYBERTEC, crear_caso_demo
from ..models import Asiento, Caso, Cuenta
from ..servicios import excel as servicio_excel
from ..servicios.casos import exportar_json, importar_asientos, importar_json
from ..servicios.pdf import CLAVES_SECCION, generar_reporte_pdf, nombre_reporte

PANTALLAS = [
    "inicio",
    "casos",
    "plan_cuentas",
    "registrar_asiento",
    "libro_diario",
    "libro_mayor",
    "balance_comprobacion",
    "estado_resultados",
    "balance_general",
    "reporte",
    "configuracion",
]


class PantallasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def test_todas_las_pantallas_abren(self):
        for nombre in PANTALLAS:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200, nombre)

    def test_sin_caso_manda_a_casos(self):
        Caso.objects.all().delete()
        respuesta = self.client.get(reverse("libro_diario"))
        self.assertRedirects(respuesta, reverse("casos"))

    def test_inicio_sin_caso_abre_igual(self):
        Caso.objects.all().delete()
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Bienvenido al Sistema y Gestión Financiera")

    def test_inicio_muestra_las_cifras_del_caso(self):
        respuesta = self.client.get(reverse("inicio"))
        self.assertContains(respuesta, "100,000.00")
        self.assertContains(respuesta, "Balance de comprobación cuadrado")

    def test_crear_caso_desde_la_pantalla(self):
        datos = {
            "accion": "nuevo",
            "nombre": "Caso de prueba",
            "razon_social": "Empresa de Prueba S.A.C.",
            "ruc": "20123456789",
            "simbolo_moneda": "S/",
            "periodo_inicio": "2024-01-01",
            "periodo_fin": "2024-12-31",
            "tasa_impuesto_renta": "29.50",
            "plantilla_cuentas": "numerado",
        }
        respuesta = self.client.post(reverse("casos"), datos)
        self.assertRedirects(respuesta, reverse("inicio"))
        caso = Caso.objects.get(nombre="Caso de prueba")
        self.assertTrue(caso.cuentas.exists())
        self.assertEqual(self.client.session["caso_activo_id"], caso.pk)

    def test_el_ruc_debe_tener_once_digitos(self):
        datos = {
            "accion": "nuevo",
            "nombre": "Caso malo",
            "razon_social": "Empresa",
            "ruc": "123",
            "simbolo_moneda": "S/",
            "tasa_impuesto_renta": "0",
            "plantilla_cuentas": "vacio",
        }
        respuesta = self.client.post(reverse("casos"), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El RUC tiene 11 dígitos")
        self.assertFalse(Caso.objects.filter(nombre="Caso malo").exists())

    def test_agregar_cuenta(self):
        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        respuesta = self.client.post(
            reverse("plan_cuentas"),
            {"codigo": "99", "nombre": "Cuenta nueva", "tipo": "ACTIVO", "rubro": "CORRIENTE"},
        )
        self.assertRedirects(respuesta, reverse("plan_cuentas"))
        self.assertTrue(self.caso.cuentas.filter(codigo="99").exists())

    def test_no_se_repite_el_codigo_de_cuenta(self):
        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        codigo = self.caso.cuentas.first().codigo
        respuesta = self.client.post(
            reverse("plan_cuentas"),
            {"codigo": codigo, "nombre": "Repetida", "tipo": "ACTIVO", "rubro": "CORRIENTE"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe una cuenta con ese código")

    def test_no_se_borra_una_cuenta_con_movimientos(self):
        cuenta = Cuenta.objects.filter(caso=self.caso, lineas__isnull=False).first()
        antes = self.caso.cuentas.count()
        self.client.post(reverse("cuenta_eliminar", args=[cuenta.pk]))
        self.assertEqual(self.caso.cuentas.count(), antes)


class AsientosTest(TestCase):
    """La regla del sistema: el asiento entra solo si Debe = Haber."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def _cuentas(self):
        caja = self.caso.cuentas.get(codigo="10")
        capital = self.caso.cuentas.get(codigo="50")
        return caja, capital

    def _datos(self, debe, haber):
        caja, capital = self._cuentas()
        return {
            "fecha": "2024-03-01",
            "glosa": "Aporte adicional de los socios",
            "lineas-TOTAL_FORMS": "2",
            "lineas-INITIAL_FORMS": "0",
            "lineas-MIN_NUM_FORMS": "0",
            "lineas-MAX_NUM_FORMS": "1000",
            "lineas-0-cuenta": str(caja.pk),
            "lineas-0-debe": debe,
            "lineas-0-haber": "0",
            "lineas-0-signo": "",
            "lineas-0-monto": "",
            "lineas-1-cuenta": str(capital.pk),
            "lineas-1-debe": "0",
            "lineas-1-haber": haber,
            "lineas-1-signo": "",
            "lineas-1-monto": "",
        }

    def test_asiento_cuadrado_se_guarda(self):
        antes = self.caso.asientos.count()
        respuesta = self.client.post(reverse("registrar_asiento"), self._datos("5000", "5000"))
        self.assertRedirects(respuesta, reverse("libro_diario"))
        self.assertEqual(self.caso.asientos.count(), antes + 1)
        asiento = self.caso.asientos.order_by("-pk").first()
        self.assertEqual(asiento.lineas.count(), 2)

    def test_asiento_descuadrado_no_se_guarda(self):
        antes = self.caso.asientos.count()
        respuesta = self.client.post(reverse("registrar_asiento"), self._datos("5000", "4000"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Debe")
        self.assertEqual(self.caso.asientos.count(), antes)

    def test_modo_de_signo(self):
        """Con signo + en una cuenta de activo, el importe va al Debe."""
        caja, capital = self._cuentas()
        datos = self._datos("0", "0")
        datos["lineas-0-signo"] = "+"
        datos["lineas-0-monto"] = "800"
        datos["lineas-1-signo"] = "+"
        datos["lineas-1-monto"] = "800"
        respuesta = self.client.post(reverse("registrar_asiento"), datos)
        self.assertRedirects(respuesta, reverse("libro_diario"))
        asiento = self.caso.asientos.order_by("-pk").first()
        linea_caja = asiento.lineas.get(cuenta=caja)
        linea_capital = asiento.lineas.get(cuenta=capital)
        self.assertEqual(linea_caja.debe, Decimal("800.00"))
        self.assertEqual(linea_caja.haber, Decimal("0.00"))
        self.assertEqual(linea_capital.haber, Decimal("800.00"))

    def test_eliminar_asiento(self):
        asiento = self.caso.asientos.first()
        self.client.post(reverse("asiento_eliminar", args=[asiento.pk]))
        self.assertFalse(Asiento.objects.filter(pk=asiento.pk).exists())


class DescargasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def test_pdf_completo(self):
        contenido = generar_reporte_pdf(self.caso.a_dominio(), CLAVES_SECCION)
        self.assertTrue(contenido.startswith(b"%PDF"))
        self.assertGreater(len(contenido), 5000)

    def test_pdf_desde_la_pantalla(self):
        respuesta = self.client.post(reverse("reporte"), {"secciones": CLAVES_SECCION})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("cybertec", respuesta["Content-Disposition"])

    def test_pdf_sin_secciones_avisa(self):
        respuesta = self.client.post(reverse("reporte"), {"secciones": []})
        self.assertEqual(respuesta.status_code, 200)

    def test_nombre_del_reporte(self):
        self.assertEqual(
            nombre_reporte(self.caso.a_dominio()), "reporte-financiero-cybertec-s-a.pdf"
        )

    def test_excel_con_una_hoja_por_reporte(self):
        import openpyxl

        contenido = servicio_excel.exportar_excel(self.caso.a_dominio())
        libro = openpyxl.load_workbook(io.BytesIO(contenido))
        self.assertEqual(
            libro.sheetnames,
            [
                "Plan de cuentas",
                "Libro Diario",
                "Libro Mayor",
                "Balance Comprobacion",
                "Estado Resultados",
                "Balance General",
            ],
        )

    def test_excel_desde_la_pantalla(self):
        respuesta = self.client.get(reverse("reporte_excel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("spreadsheetml", respuesta["Content-Type"])

    def test_plantilla_de_asientos(self):
        respuesta = self.client.get(reverse("plantilla_asientos"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("plantilla-asientos.xlsx", respuesta["Content-Disposition"])

    def test_respaldo_json_ida_y_vuelta(self):
        datos = exportar_json(self.caso)
        copia = importar_json(datos["caso"])
        self.assertEqual(copia.cuentas.count(), self.caso.cuentas.count())
        self.assertEqual(copia.asientos.count(), self.caso.asientos.count())
        original = self.caso.a_dominio()
        clon = copia.a_dominio()
        from ..dominio.balance_comprobacion import construir_balance_comprobacion

        self.assertEqual(
            construir_balance_comprobacion(clon).total_debe,
            construir_balance_comprobacion(original).total_debe,
        )

    def test_importar_caso_desde_la_pantalla(self):
        datos = json.dumps(exportar_json(self.caso)).encode("utf-8")
        archivo = io.BytesIO(datos)
        archivo.name = "caso.json"
        respuesta = self.client.post(reverse("caso_importar"), {"archivo": archivo})
        self.assertRedirects(respuesta, reverse("inicio"))
        self.assertEqual(Caso.objects.count(), 2)


class ImportarAsientosTest(TestCase):
    """pandas lee el archivo; el motor decide si el asiento entra."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def _csv(self, texto: str):
        archivo = io.BytesIO(texto.encode("utf-8"))
        archivo.name = "asientos.csv"
        return archivo

    def test_lee_un_csv_y_agrupa_por_numero(self):
        archivo = self._csv(
            "numero,fecha,glosa,codigo,debe,haber\n"
            "1,05/03/2024,Aporte extra,10,3000,0\n"
            "1,05/03/2024,Aporte extra,50,0,3000\n"
        )
        leidos = servicio_excel.leer_asientos(archivo, "asientos.csv")
        self.assertEqual(len(leidos), 1)
        self.assertEqual(len(leidos[0]["lineas"]), 2)
        self.assertEqual(leidos[0]["lineas"][0]["debe"], Decimal("3000.00"))

    def test_importa_lo_que_cuadra_y_avisa_lo_que_no(self):
        archivo = self._csv(
            "numero,fecha,glosa,codigo,debe,haber\n"
            "1,05/03/2024,Aporte extra,10,3000,0\n"
            "1,05/03/2024,Aporte extra,50,0,3000\n"
            "2,06/03/2024,Asiento torcido,10,1000,0\n"
            "2,06/03/2024,Asiento torcido,50,0,900\n"
        )
        leidos = servicio_excel.leer_asientos(archivo, "asientos.csv")
        antes = self.caso.asientos.count()
        resultado = importar_asientos(self.caso, leidos)
        self.assertEqual(resultado.importados, 1)
        self.assertEqual(len(resultado.errores), 1)
        self.assertEqual(self.caso.asientos.count(), antes + 1)

    def test_una_cuenta_que_no_existe_se_informa(self):
        archivo = self._csv(
            "numero,fecha,glosa,codigo,debe,haber\n"
            "1,05/03/2024,Con cuenta rara,ZZZ,100,0\n"
            "1,05/03/2024,Con cuenta rara,50,0,100\n"
        )
        leidos = servicio_excel.leer_asientos(archivo, "asientos.csv")
        resultado = importar_asientos(self.caso, leidos)
        self.assertEqual(resultado.importados, 0)
        self.assertIn("ZZZ", resultado.errores[0])

    def test_puede_crear_las_cuentas_que_faltan(self):
        archivo = self._csv(
            "numero,fecha,glosa,codigo,debe,haber\n"
            "1,05/03/2024,Con cuenta nueva,ZZZ,100,0\n"
            "1,05/03/2024,Con cuenta nueva,50,0,100\n"
        )
        leidos = servicio_excel.leer_asientos(archivo, "asientos.csv")
        resultado = importar_asientos(self.caso, leidos, crear_cuentas=True)
        self.assertEqual(resultado.importados, 1)
        self.assertTrue(self.caso.cuentas.filter(codigo="ZZZ").exists())

    def test_acepta_otros_nombres_de_columna(self):
        archivo = self._csv(
            "Nro,Fecha,Descripcion,Cuenta,Cargo,Abono\n"
            "7,05/03/2024,Con alias,10,500,0\n"
            "7,05/03/2024,Con alias,50,0,500\n"
        )
        leidos = servicio_excel.leer_asientos(archivo, "asientos.csv")
        self.assertEqual(len(leidos), 1)
        self.assertEqual(leidos[0]["glosa"], "Con alias")

    def test_un_archivo_sin_las_columnas_necesarias_falla_claro(self):
        archivo = self._csv("algo,otra\n1,2\n")
        with self.assertRaises(ValueError) as error:
            servicio_excel.leer_asientos(archivo, "asientos.csv")
        self.assertIn("faltan columnas", str(error.exception))

    def test_importar_desde_la_pantalla(self):
        archivo = self._csv(
            "numero,fecha,glosa,codigo,debe,haber\n"
            "1,05/03/2024,Desde la pantalla,10,250,0\n"
            "1,05/03/2024,Desde la pantalla,50,0,250\n"
        )
        antes = self.caso.asientos.count()
        respuesta = self.client.post(reverse("asientos_importar"), {"archivo": archivo})
        self.assertRedirects(respuesta, reverse("libro_diario"))
        self.assertEqual(self.caso.asientos.count(), antes + 1)


class CargarDemoTest(TestCase):
    """El despliegue llama a cargar_demo --si-vacio en cada versión nueva."""

    def test_base_vacia_carga_los_ejemplos(self):
        from django.core.management import call_command

        from ..datos.casos_demo import PLANTILLAS_CASO

        call_command("cargar_demo", si_vacio=True, stdout=io.StringIO())
        self.assertEqual(Caso.objects.count(), len(PLANTILLAS_CASO))

    def test_con_casos_guardados_no_toca_nada(self):
        from django.core.management import call_command

        crear_caso_demo(CYBERTEC)
        call_command("cargar_demo", si_vacio=True, stdout=io.StringIO())
        self.assertEqual(Caso.objects.count(), 1)
