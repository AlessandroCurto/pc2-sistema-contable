"""Pruebas del lector de enunciados.

El caso largo es el mismo que resolvió el profesor en clase, así que las cifras
esperadas están verificadas a mano y coinciden con las del caso de ejemplo
"Comercializadora del Sur S.A.C." que ya vive en datos/casos_demo.py.
"""

import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from ..datos.casos_demo import COMERCIALIZADORA_SUR, CYBERTEC, crear_caso_demo
from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..servicios import enunciados

ENUNCIADO = """La empresa Comercializadora del Sur S.A.C. presenta el siguiente inventario \
inicial al 01 de junio del 2024: dinero en efectivo S/. 2,500,000, cuenta corriente \
S/. 3,500,000, Clientes S/. 600,000, Proveedores S/. 800,000 y capital S/. 5,800,000.
01/06/2024 - Compra de Mercadería: Se compran mercaderías a Adelco Ltda. por un total de \
S/ 1,000,000.00 (IGV incluido). El pago se fracciona firmando 10 letras de cambio de igual valor.
02/06/2024 - Venta de Mercadería: Se venden mercaderías a Mario Cea Castro por un valor neto \
de S/ 400,000.00 (más IGV). El cliente cancela el 40% del monto total facturado en efectivo y \
por el saldo acepta 4 letras de cambio (N.º 101, 102, 103 y 104).
10/06/2024 - Gasto Operativo: Se paga el arriendo mensual de la oficina por S/ 100,000.00 \
netos. La operación se cancela con cheque (salida de cuenta corriente).
11/06/2024 - Amortización de Deuda: Se cancela el 50% de la deuda histórica (inventario \
inicial) que se mantenía con los proveedores, emitiendo un cheque.
15/06/2024 - Cobranza a Clientes: El cliente Mario Cea Castro cancela con cheque las letras \
N.º 101 y 102 derivadas de la venta del 02 de junio.
30/06/2024 - Pago de Letras: La empresa cancela con cheque 3 de las letras pendientes a favor \
del proveedor Adelco Ltda.
30/06/2024 - Ajuste por Costo de Ventas: Al cierre del mes, el conteo físico determina una \
existencia final de mercaderías valorizada en S/ 690,360.00."""


class LeerElCasoCompletoTest(TestCase):
    """El enunciado de clase, de principio a fin."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.caso.asientos.all().delete()  # se parte de un caso vacío
        cls.dominio = cls.caso.a_dominio()
        cls.lectura = enunciados.leer(ENUNCIADO, cls.dominio)

    def _asiento(self, parte_de_la_glosa):
        # Ojo: "inventario" contiene "venta", por eso los trozos son largos.
        for asiento in self.lectura.asientos:
            if parte_de_la_glosa.lower() in asiento.glosa.lower():
                return asiento
        self.fail("no se leyó el asiento de " + parte_de_la_glosa)

    def _monto(self, glosa, codigo):
        for linea in self._asiento(glosa).lineas:
            if linea.cuenta.codigo == codigo:
                return linea.debe or linea.haber
        self.fail(f"el asiento de {glosa} no movió la cuenta {codigo}")

    def test_lee_las_ocho_operaciones_sin_problemas(self):
        self.assertEqual(len(self.lectura.asientos), 8)
        self.assertEqual(self.lectura.problemas, [])

    def test_todos_los_asientos_cuadran(self):
        for asiento in self.lectura.asientos:
            self.assertTrue(asiento.cuadra, asiento.glosa)

    def test_la_suma_del_debe_es_la_correcta(self):
        total = sum((a.total for a in self.lectura.asientos), Decimal("0.00"))
        self.assertEqual(total, Decimal("9170697.63"))

    def test_apertura_reparte_segun_el_tipo_de_cuenta(self):
        apertura = self._asiento("inventario inicial")
        debe = {l.cuenta.codigo: l.debe for l in apertura.lineas if l.debe}
        haber = {l.cuenta.codigo: l.haber for l in apertura.lineas if l.haber}
        self.assertEqual(debe["101"], Decimal("2500000"))   # caja, activo
        self.assertEqual(debe["102"], Decimal("3500000"))   # banco, activo
        self.assertEqual(debe["103"], Decimal("600000"))    # clientes, activo
        self.assertEqual(haber["201"], Decimal("800000"))   # proveedores, pasivo
        self.assertEqual(haber["301"], Decimal("5800000"))  # capital, patrimonio

    def test_separa_el_igv_incluido_de_la_compra(self):
        self.assertEqual(self._monto("compra de mercader", "105"), Decimal("847457.63"))
        self.assertEqual(self._monto("compra de mercader", "106"), Decimal("152542.37"))
        self.assertEqual(self._monto("compra de mercader", "202"), Decimal("1000000.00"))

    def test_agrega_el_igv_a_la_venta_y_parte_el_cobro(self):
        self.assertEqual(self._monto("venta de mercader", "401"), Decimal("400000.00"))
        self.assertEqual(self._monto("venta de mercader", "203"), Decimal("72000.00"))
        self.assertEqual(self._monto("venta de mercader", "101"), Decimal("188800.00"))   # 40%
        self.assertEqual(self._monto("venta de mercader", "104"), Decimal("283200.00"))   # 4 letras

    def test_el_porcentaje_sale_del_saldo_inicial_de_proveedores(self):
        """El 50% de la deuda: hay que recordar los 800,000 de la apertura."""
        self.assertEqual(self._monto("pago a proveedores", "201"), Decimal("400000.00"))

    def test_el_valor_de_las_letras_sale_de_la_operacion_que_las_emitio(self):
        # Cobro de 2 letras de la venta: 283,200 / 4 = 70,800 cada una.
        self.assertEqual(self._monto("cobro de letras", "104"), Decimal("141600.00"))
        # Pago de 3 letras de la compra: 1,000,000 / 10 = 100,000 cada una.
        self.assertEqual(self._monto("pago de letras", "202"), Decimal("300000.00"))

    def test_el_costo_de_ventas_sale_por_diferencia(self):
        self.assertEqual(self._monto("costo de ventas", "502"), Decimal("157097.63"))

    def test_explica_de_donde_sale_cada_numero(self):
        texto = enunciados.a_markdown(self.lectura, self.dominio)
        self.assertIn("1.18", texto)        # cómo sacó la base del IGV
        self.assertIn("70,800.00", texto)   # el valor de cada letra
        self.assertIn("9,170,697.63", texto)

    def test_registrarlos_deja_el_caso_cuadrado(self):
        from ..servicios.casos import importar_asientos

        resultado = importar_asientos(
            self.caso, enunciados.a_importables(self.lectura, self.dominio)
        )
        self.assertEqual(resultado.importados, 8)
        self.assertEqual(resultado.errores, [])
        balance = construir_balance_comprobacion(self.caso.a_dominio())
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("9170697.63"))


class CasosSueltosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.dominio = cls.caso.a_dominio()

    def _una(self, texto):
        lectura = enunciados.leer(texto, self.dominio)
        self.assertEqual(len(lectura.asientos), 1, lectura.problemas)
        return lectura.asientos[0]

    def test_compra_al_contado_sin_igv(self):
        asiento = self._una(
            "05/06/2024 - Se compran mercaderías por S/ 50,000.00 pagando en efectivo."
        )
        montos = {l.cuenta.codigo: (l.debe, l.haber) for l in asiento.lineas}
        self.assertEqual(montos["105"][0], Decimal("50000.00"))
        self.assertEqual(montos["101"][1], Decimal("50000.00"))

    def test_venta_al_credito(self):
        asiento = self._una(
            "06/06/2024 - Se venden mercaderías al crédito por S/ 10,000.00 más IGV."
        )
        montos = {l.cuenta.codigo: (l.debe, l.haber) for l in asiento.lineas}
        self.assertEqual(montos["103"][0], Decimal("11800.00"))  # clientes
        self.assertEqual(montos["401"][1], Decimal("10000.00"))
        self.assertEqual(montos["203"][1], Decimal("1800.00"))

    def test_el_igv_incluido_se_separa_al_reves(self):
        asiento = self._una(
            "07/06/2024 - Se compran mercaderías por S/ 11,800.00 (IGV incluido), al contado."
        )
        montos = {l.cuenta.codigo: l.debe for l in asiento.lineas if l.debe}
        self.assertEqual(montos["105"], Decimal("10000.00"))
        self.assertEqual(montos["106"], Decimal("1800.00"))

    def test_una_operacion_que_no_entiende_la_informa(self):
        lectura = enunciados.leer(
            "08/06/2024 - Se firma un contrato de arrendamiento financiero por un "
            "terreno valorizado en S/ 500,000.00 con opción de compra.",
            self.dominio,
        )
        self.assertEqual(lectura.asientos, [])
        self.assertEqual(len(lectura.problemas), 1)

    def test_avisa_cuando_falta_el_dato_de_las_letras(self):
        """Sin la venta previa no se puede saber cuánto vale cada letra."""
        lectura = enunciados.leer(
            "15/06/2024 - Cobranza: el cliente cancela con cheque 2 letras.", self.dominio
        )
        self.assertEqual(lectura.asientos, [])
        self.assertIn("no se leyó antes", lectura.problemas[0])

    def test_avisa_si_las_fechas_mezclan_anios(self):
        lectura = enunciados.leer(
            "01/06/2024 - Se compran mercaderías por S/ 1,000.00 al contado.\n"
            "30/06/2025 - Se compran mercaderías por S/ 2,000.00 al contado.",
            self.dominio,
        )
        self.assertTrue(any("error de tipeo" in a for a in lectura.avisos))

    def test_la_deuda_de_los_clientes_es_cobranza_no_pago(self):
        """El texto dice "deuda histórica", pero la deben los clientes."""
        asiento = self._una(
            "20/08/2024 - Cobranza a Clientes: Se cobra con cheque S/ 200,000.00 de la "
            "deuda histórica que mantenían los clientes del inventario inicial."
        )
        montos = {l.cuenta.codigo: (l.debe, l.haber) for l in asiento.lineas}
        self.assertEqual(montos["102"][0], Decimal("200000.00"))   # entra al banco
        self.assertEqual(montos["103"][1], Decimal("200000.00"))   # baja clientes
        self.assertNotIn("201", montos)                            # no toca proveedores

    def test_la_deuda_con_proveedores_sigue_siendo_pago(self):
        """Hace falta la apertura: el porcentaje se calcula sobre ese saldo."""
        lectura = enunciados.leer(
            "La empresa X S.A.C. presenta el siguiente inventario inicial: "
            "dinero en efectivo S/ 800,000, Mercaderías S/ 200,000, "
            "Proveedores S/ 800,000 y capital S/ 200,000.\n"
            "25/08/2024 - Amortización: Se cancela el 20% de la deuda histórica "
            "(inventario inicial) que se mantenía con los proveedores, con cheque.",
            self.dominio,
        )
        self.assertEqual(len(lectura.asientos), 2, lectura.problemas)
        montos = {l.cuenta.codigo: (l.debe, l.haber) for l in lectura.asientos[1].lineas}
        self.assertEqual(montos["201"][0], Decimal("160000.00"))   # 20% de 800,000

    def test_venta_al_contado_sin_letras(self):
        asiento = self._una(
            "05/08/2024 - Venta al contado: Se venden mercaderías por un valor neto de "
            "S/ 250,000.00 (más IGV). El cliente paga en efectivo."
        )
        montos = {l.cuenta.codigo: (l.debe, l.haber) for l in asiento.lineas}
        self.assertEqual(montos["101"][0], Decimal("295000.00"))
        self.assertEqual(montos["401"][1], Decimal("250000.00"))
        self.assertEqual(montos["203"][1], Decimal("45000.00"))

    def test_los_sueldos_no_van_a_la_cuenta_de_arriendo(self):
        asiento = self._una(
            "15/08/2024 - Se pagan los sueldos del mes por S/ 90,000.00 mediante cheque."
        )
        nombres = [l.cuenta.nombre for l in asiento.lineas if l.debe]
        self.assertIn("Personal", nombres[0])

    def test_lee_la_fecha_escrita_con_letras(self):
        datos = enunciados.datos_del_caso(
            "La empresa Ferretería Los Andes S.R.L. presenta el siguiente inventario "
            "inicial al 01 de agosto del 2024: efectivo S/ 900,000 y capital S/ 900,000.\n"
            "31/08/2024 - Se pagan los sueldos por S/ 1,000.00 con cheque."
        )
        self.assertEqual(datos["nombre"], "Ferretería Los Andes S.R.L.")
        self.assertEqual(datos["periodo_inicio"].isoformat(), "2024-08-01")
        self.assertEqual(datos["periodo_fin"].isoformat(), "2024-08-31")

    def test_reconoce_un_enunciado_y_descarta_una_pregunta(self):
        self.assertTrue(enunciados.parece_enunciado(ENUNCIADO))
        self.assertFalse(enunciados.parece_enunciado("como registro un asiento"))
        self.assertFalse(enunciados.parece_enunciado("hola"))


class AsistenteConEnunciadoTest(TestCase):
    """El enunciado llega por el chat y se registra con el botón."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def test_sin_caso_abierto_prepara_uno_con_el_nombre_del_enunciado(self):
        from ..servicios import asistente
        from ..models import Caso

        Caso.objects.all().delete()
        respuesta = asistente.responder(ENUNCIADO, None)
        self.assertIn("Comercializadora del Sur S.A.C.", respuesta)
        self.assertIn("847,457.63", respuesta)

    def test_sin_caso_el_boton_crea_el_caso_entero(self):
        from ..models import Caso

        Caso.objects.all().delete()
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": ENUNCIADO}),
            content_type="application/json",
        )
        datos = respuesta.json()
        self.assertEqual(datos["guardados"], 8)
        self.assertEqual(datos["caso"], "Comercializadora del Sur S.A.C.")
        caso = Caso.objects.get()
        self.assertEqual(caso.asientos.count(), 8)
        self.assertEqual(caso.periodo_inicio.isoformat(), "2024-06-01")
        self.assertEqual(caso.periodo_fin.isoformat(), "2024-06-30")
        balance = construir_balance_comprobacion(caso.a_dominio())
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("9170697.63"))

    def test_completa_las_cuentas_que_le_faltan_al_plan(self):
        """CYBERTEC usa el PCGE: no tiene letras ni cuentas de IGV.

        El enunciado nombra a la misma empresa, así que se agrega a su caso y
        hay que completarle el plan de cuentas.
        """
        from ..models import Caso

        Caso.objects.all().delete()
        caso = crear_caso_demo(CYBERTEC)
        caso.asientos.all().delete()
        self.client.post(reverse("caso_abrir", args=[caso.pk]))
        antes = caso.cuentas.count()
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": ENUNCIADO.replace(
                "Comercializadora del Sur S.A.C.", "CYBERTEC S.A."
            )}),
            content_type="application/json",
        )
        datos = respuesta.json()
        self.assertEqual(datos["caso"], "")            # no creó otro caso
        self.assertEqual(datos["guardados"], 8)
        self.assertGreater(datos["cuentas"], 0)
        self.assertGreater(caso.cuentas.count(), antes)
        self.assertTrue(caso.cuentas.filter(nombre="Letras por Cobrar").exists())
        balance = construir_balance_comprobacion(caso.a_dominio())
        self.assertTrue(balance.cuadrado)

    def test_las_cuentas_nuevas_nacen_con_su_tipo_correcto(self):
        from ..models import Caso

        Caso.objects.all().delete()
        self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": ENUNCIADO}),
            content_type="application/json",
        )
        caso = Caso.objects.get()
        tipos = {c.nombre: c.tipo for c in caso.cuentas.all()}
        self.assertEqual(tipos["Letras por Pagar"], "PASIVO")
        self.assertEqual(tipos["IGV Crédito Fiscal"], "ACTIVO")
        self.assertEqual(tipos["Capital"], "PATRIMONIO")
        self.assertEqual(tipos["Ventas"], "INGRESO")
        self.assertEqual(tipos["Costo de Ventas"], "GASTO")

    def test_el_chat_ofrece_registrar(self):
        caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        self.client.post(reverse("caso_abrir", args=[caso.pk]))
        respuesta = self.client.post(
            reverse("chatbot"),
            data=json.dumps({"mensajes": [{"role": "user", "content": ENUNCIADO}]}),
            content_type="application/json",
        )
        cuerpo = b"".join(respuesta.streaming_content).decode("utf-8")
        self.assertIn("847,457.63", cuerpo)
        self.assertIn('"accion": "registrar"', cuerpo)

    def test_el_boton_guarda_los_asientos(self):
        caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        caso.asientos.all().delete()
        self.client.post(reverse("caso_abrir", args=[caso.pk]))
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": ENUNCIADO}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["guardados"], 8)
        self.assertEqual(datos["errores"], [])
        self.assertEqual(caso.asientos.count(), 8)

    def test_no_registra_sin_texto(self):
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": "   "}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_registra_lo_que_no_son_asientos(self):
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": "hola que tal, como estas hoy dia"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)


class ElLectorCoincideConElCasoGuardadoTest(TestCase):
    """Comprobación cruzada: el enunciado de Los Andes, leído por el asistente,
    tiene que dar exactamente el caso de ejemplo escrito a mano."""

    ENUNCIADO_ANDES = (
        "La empresa Ferretería Los Andes S.R.L. presenta el siguiente inventario inicial "
        "al 01 de agosto del 2024: dinero en efectivo S/ 900,000, cuenta corriente "
        "S/ 1,500,000, Mercaderías S/ 480,000, Clientes S/ 320,000, Proveedores "
        "S/ 500,000 y capital S/ 2,700,000.\n"
        "02/08/2024 - Compra de Mercadería: Se compran mercaderías a Aceros del Centro "
        "S.A. por un total de S/ 354,000.00 (IGV incluido), cancelando con cheque.\n"
        "05/08/2024 - Venta al contado: Se venden mercaderías por un valor neto de "
        "S/ 250,000.00 (más IGV). El cliente paga en efectivo.\n"
        "12/08/2024 - Venta al crédito: Se venden mercaderías a Constructora Huaraz "
        "E.I.R.L. por un valor neto de S/ 180,000.00 (más IGV), otorgando crédito a 30 días.\n"
        "15/08/2024 - Gasto de Personal: Se pagan los sueldos del mes por S/ 90,000.00 "
        "mediante cheque.\n"
        "20/08/2024 - Cobranza a Clientes: Se cobra con cheque S/ 200,000.00 de la deuda "
        "histórica que mantenían los clientes del inventario inicial.\n"
        "25/08/2024 - Amortización de Deuda: Se cancela el 60% de la deuda histórica "
        "(inventario inicial) que se mantenía con los proveedores, emitiendo un cheque.\n"
        "31/08/2024 - Ajuste por Costo de Ventas: Al cierre del mes, el conteo físico "
        "determina una existencia final de mercaderías valorizada en S/ 540,000.00."
    )

    def test_leerlo_da_los_mismos_movimientos_que_el_caso_de_ejemplo(self):
        from ..datos.casos_demo import LOS_ANDES, crear_caso_demo

        a_mano = crear_caso_demo(LOS_ANDES)
        esperado = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in a_mano.asientos.all()
            for linea in asiento.lineas.all()
        )

        a_mano.asientos.all().delete()
        lectura = enunciados.leer(self.ENUNCIADO_ANDES, a_mano.a_dominio())
        leido = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in lectura.asientos
            for linea in asiento.lineas
        )
        self.assertEqual(leido, esperado)


class NoMezclarDosEmpresasTest(TestCase):
    """Pegar el enunciado de otra empresa no debe ensuciar el caso abierto."""

    OTRA = (
        "La empresa Comercial Pacífico S.A.C. presenta el siguiente inventario inicial "
        "al 01 de setiembre del 2024: dinero en efectivo S/ 1,200,000, cuenta corriente "
        "S/ 2,800,000, Mercaderías S/ 600,000, Proveedores S/ 700,000 y capital "
        "S/ 3,900,000.\n"
        "03/09/2024 - Se compran mercaderías por S/ 1,180,000.00 (IGV incluido), "
        "firmando 8 letras de cambio de igual valor.\n"
        "12/09/2024 - Se paga el arriendo del almacén por S/ 120,000.00 netos con cheque."
    )

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)

    def _registrar(self, texto):
        return self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": texto}),
            content_type="application/json",
        ).json()

    def test_otra_empresa_va_a_un_caso_nuevo(self):
        from ..models import Caso

        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        antes = self.caso.asientos.count()
        datos = self._registrar(self.OTRA)

        self.assertEqual(datos["caso"], "Comercial Pacífico S.A.C.")
        self.assertEqual(self.caso.asientos.count(), antes)  # intacto
        nuevo = Caso.objects.get(nombre="Comercial Pacífico S.A.C.")
        self.assertEqual(nuevo.asientos.count(), 3)
        self.assertEqual(Caso.objects.count(), 2)

    def test_el_caso_nuevo_queda_abierto(self):
        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        self._registrar(self.OTRA)
        respuesta = self.client.get(reverse("inicio"))
        self.assertContains(respuesta, "Comercial Pacífico S.A.C.")

    def test_la_misma_empresa_si_se_agrega_al_caso_abierto(self):
        from ..models import Caso

        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        antes = self.caso.asientos.count()
        datos = self._registrar(
            "La empresa Comercializadora del Sur S.A.C. informa: "
            "05/07/2024 - Se paga el arriendo por S/ 5,000.00 netos con cheque."
        )
        self.assertEqual(datos["caso"], "")           # no creó ninguno
        self.assertEqual(Caso.objects.count(), 1)
        self.assertEqual(self.caso.asientos.count(), antes + 1)

    def test_un_enunciado_sin_empresa_sigue_en_el_caso_abierto(self):
        from ..models import Caso

        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        antes = self.caso.asientos.count()
        self._registrar("05/07/2024 - Se paga el arriendo por S/ 5,000.00 netos con cheque.")
        self.assertEqual(Caso.objects.count(), 1)
        self.assertEqual(self.caso.asientos.count(), antes + 1)

    def test_el_aviso_lo_dice_antes_de_registrar(self):
        from ..servicios import asistente

        respuesta = asistente.responder(self.OTRA, self.caso.a_dominio())
        self.assertIn("Comercial Pacífico S.A.C.", respuesta)
        self.assertIn("caso aparte", respuesta)
