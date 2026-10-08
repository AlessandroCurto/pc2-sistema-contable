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

    def test_un_cobro_con_cheque_entra_al_banco_y_no_a_la_caja(self):
        """Lo detectó un compañero: la glosa decía cheque y cargaba a Caja."""
        asiento = self._asiento("cobro de letras")
        destinos = [l.cuenta.codigo for l in asiento.lineas if l.debe]
        self.assertEqual(destinos, ["102"])          # Banco
        self.assertNotIn("101", destinos)            # no Caja

    def test_coincide_con_el_caso_de_ejemplo_guardado(self):
        """El caso escrito a mano y lo que se lee del enunciado no pueden diferir."""
        from ..datos.casos_demo import COMERCIALIZADORA_SUR, crear_caso_demo

        guardado = crear_caso_demo(COMERCIALIZADORA_SUR)
        a_mano = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in guardado.asientos.all()
            for linea in asiento.lineas.all()
        )
        leido = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in self.lectura.asientos
            for linea in asiento.lineas
        )
        self.assertEqual(leido, a_mano)

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


class ElCasoCreadoNaceCompletoTest(TestCase):
    """Un caso creado desde el chat tiene que quedar listo para usarse.

    Sin tasa de impuesto, la utilidad neta salía igual a la utilidad antes de
    impuesto y el estudiante veía una cifra que no era la suya.
    """

    PACIFICO = (
        "La empresa Comercial Pacífico S.A.C. presenta el siguiente inventario inicial "
        "al 01 de setiembre del 2024: dinero en efectivo S/ 1,200,000, cuenta corriente "
        "S/ 2,800,000, Mercaderías S/ 600,000, Clientes S/ 400,000, Proveedores "
        "S/ 700,000 y capital S/ 4,300,000.\n"
        "03/09/2024 - Compra de Mercadería: Se compran mercaderías por un total de "
        "S/ 1,180,000.00 (IGV incluido), firmando 8 letras de cambio de igual valor.\n"
        "06/09/2024 - Venta de Mercadería: Se venden mercaderías por un valor neto de "
        "S/ 700,000.00 (más IGV). El cliente cancela el 50% del monto total facturado en "
        "efectivo y por el saldo acepta 4 letras de cambio (N.º 301, 302, 303 y 304).\n"
        "12/09/2024 - Gasto Operativo: Se paga el arriendo mensual del almacén por "
        "S/ 120,000.00 netos. La operación se cancela con cheque.\n"
        "18/09/2024 - Amortización de Deuda: Se cancela el 50% de la deuda histórica "
        "(inventario inicial) que se mantenía con los proveedores, emitiendo un cheque.\n"
        "30/09/2024 - Ajuste por Costo de Ventas: Al cierre del mes, el conteo físico "
        "determina una existencia final de mercaderías valorizada en S/ 1,160,000.00."
    )

    def _registrar(self, texto):
        from ..models import Caso

        Caso.objects.all().delete()
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": texto}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        return Caso.objects.get()

    def test_nace_con_la_tasa_de_tercera_categoria(self):
        caso = self._registrar(self.PACIFICO)
        self.assertEqual(caso.tasa_impuesto_renta, Decimal("29.50"))
        self.assertTrue(caso.impuesto_afecta_patrimonio)

    def test_la_utilidad_neta_no_es_la_de_antes_de_impuesto(self):
        from ..dominio.estado_resultados import construir_estado_resultados

        caso = self._registrar(self.PACIFICO)
        estado = construir_estado_resultados(caso.a_dominio())
        self.assertEqual(estado.resultado_antes_impuesto, Decimal("140000.00"))
        self.assertEqual(estado.impuesto, Decimal("41300.00"))
        self.assertEqual(estado.utilidad_neta, Decimal("98700.00"))
        self.assertNotEqual(estado.utilidad_neta, estado.resultado_antes_impuesto)

    def test_el_asistente_responde_esa_utilidad(self):
        from ..servicios import asistente

        caso = self._registrar(self.PACIFICO)
        respuesta = asistente.responder("¿cuál es mi utilidad neta?", caso.a_dominio())
        self.assertIn("98,700.00", respuesta)
        self.assertIn("(29.50%)", respuesta)

    def test_el_impuesto_queda_en_el_pasivo(self):
        from ..dominio.balance_general import construir_balance_general

        caso = self._registrar(self.PACIFICO)
        general = construir_balance_general(caso.a_dominio())
        self.assertEqual(general.impuesto_por_pagar, Decimal("41300.00"))
        self.assertTrue(general.cuadrado)

    def test_si_el_enunciado_da_otra_tasa_se_usa_esa(self):
        caso = self._registrar(
            self.PACIFICO + "\nLa empresa aplica un impuesto a la renta del 30%."
        )
        self.assertEqual(caso.tasa_impuesto_renta, Decimal("30.00"))


class LaRedaccionNuevaDelEnunciadoTest(TestCase):
    """El enunciado se reescribió con los importes explícitos. Debe dar lo mismo."""

    REDACTADO = (
        "La empresa Comercializadora del Sur S.A.C. presenta el siguiente inventario "
        "inicial al 01 de junio del 2024: dinero en efectivo S/. 2,500,000, cuenta "
        "corriente S/. 3,500,000, Clientes S/. 600,000, Proveedores S/. 800,000 y "
        "capital S/. 5,800,000.\n"
        "01/06/2024 – Compra de Mercadería: Se compran mercaderías a Adelco Ltda. por un "
        "total de S/ 1,000,000.00 (IGV incluido), fraccionando el pago en 10 letras de "
        "cambio de igual valor.\n"
        "02/06/2024 – Venta de Mercadería: Se venden mercaderías a Mario Cea Castro por "
        "un valor neto de S/ 400,000.00 (más IGV). El cliente cancela el 40% del monto "
        "total facturado en efectivo y por el saldo acepta 4 letras de cambio "
        "(N.º 101, 102, 103 y 104).\n"
        "10/06/2024 – Gasto Operativo: Pago del arriendo mensual de la oficina con "
        "cheque por S/ 100,000.00.\n"
        "11/06/2024 – Amortización de Deuda: Pago con cheque del 50% de la deuda inicial "
        "con proveedores por S/ 400,000.00.\n"
        "15/06/2024 – Cobranza a Clientes: Cobro con cheque de las letras 101 y 102 de "
        "Mario Cea Castro por un importe de S/ 141,600.00.\n"
        "30/06/2024 – Pago de Letras: Pago con cheque de 3 letras a Adelco Ltda. por un "
        "importe de S/ 300,000.00.\n"
        "30/06/2024 – Ajuste por Costo de Ventas: Costo de ventas por diferencia de "
        "inventarios al cierre del mes considerando una existencia final de "
        "S/ 690,360.00 (asiento registrado por un importe de S/ 157,097.63)."
    )

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)

    def test_da_el_mismo_caso_que_la_redaccion_anterior(self):
        a_mano = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in self.caso.asientos.all()
            for linea in asiento.lineas.all()
        )
        self.caso.asientos.all().delete()
        lectura = enunciados.leer(self.REDACTADO, self.caso.a_dominio())
        self.assertEqual(lectura.problemas, [])
        leido = sorted(
            (linea.cuenta.codigo, linea.debe, linea.haber)
            for asiento in lectura.asientos
            for linea in asiento.lineas
        )
        self.assertEqual(leido, a_mano)

    def test_el_costo_no_se_confunde_con_la_existencia_final(self):
        """La operación trae dos importes: 690,360 es el inventario, no el costo."""
        self.caso.asientos.all().delete()
        lectura = enunciados.leer(self.REDACTADO, self.caso.a_dominio())
        costo = next(a for a in lectura.asientos if "Costo" in a.glosa)
        self.assertEqual(costo.total, Decimal("157097.63"))

    def test_el_cobro_con_cheque_va_al_banco(self):
        self.caso.asientos.all().delete()
        lectura = enunciados.leer(self.REDACTADO, self.caso.a_dominio())
        cobro = next(a for a in lectura.asientos if "Cobro" in a.glosa)
        self.assertEqual([l.cuenta.codigo for l in cobro.lineas if l.debe], ["102"])


class GenerarUnCasoTest(TestCase):
    """«Genérame un caso» tiene que entregar uno resoluble, no un texto bonito."""

    def test_el_generador_siempre_entrega_uno_valido(self):
        from ..servicios import generador

        for semilla in range(25):
            with self.subTest(semilla=semilla):
                caso = generador.generar(semilla=semilla)
                self.assertIsNotNone(caso, "no logró generar con esa semilla")
                self.assertEqual(caso.asientos, 8)
                self.assertGreater(caso.utilidad_neta, 0)

    def test_lo_que_genera_lo_sabe_leer(self):
        """Se genera con el mismo lector con el que se resuelve: no pueden diferir."""
        from ..servicios import generador

        for semilla in (0, 5, 11, 19):
            with self.subTest(semilla=semilla):
                caso = generador.generar(semilla=semilla)
                lectura = enunciados.leer(caso.enunciado, enunciados.CASO_VACIO)
                self.assertEqual(lectura.problemas, [])
                self.assertEqual(len(lectura.asientos), 8)
                for asiento in lectura.asientos:
                    self.assertTrue(asiento.cuadra, asiento.glosa)

    def test_cada_caso_es_distinto(self):
        from ..servicios import generador

        empresas = {generador.generar(semilla=s).empresa for s in range(12)}
        self.assertGreater(len(empresas), 6)

    def test_el_nombre_de_la_empresa_sale_entero(self):
        """«Inversiones Santa Rosa S.A.C.» se cortaba en «Inversiones Sa»."""
        datos = enunciados.datos_del_caso(
            "La empresa Inversiones Santa Rosa S.A.C. presenta el siguiente inventario "
            "inicial: efectivo S/ 100, Clientes S/ 100 y capital S/ 200."
        )
        self.assertEqual(datos["nombre"], "Inversiones Santa Rosa S.A.C.")

    def test_el_chat_lo_genera_y_ofrece_registrarlo(self):
        from ..servicios import asistente

        for pregunta in ("genérame un caso", "inventa un enunciado", "dame un caso al azar",
                         "crea un ejercicio nuevo", "caso aleatorio"):
            with self.subTest(pregunta=pregunta):
                self.assertTrue(asistente.pide_caso_nuevo(pregunta))

        respuesta = self.client.post(
            reverse("chatbot"),
            data=json.dumps({"mensajes": [{"role": "user", "content": "genérame un caso"}]}),
            content_type="application/json",
        )
        cuerpo = b"".join(respuesta.streaming_content).decode("utf-8")
        self.assertIn("Te arm\u00e9 un caso nuevo", cuerpo)
        self.assertIn('"accion": "registrar"', cuerpo)

    def test_no_confunde_otras_peticiones(self):
        from ..servicios import asistente

        for pregunta in ("como creo un caso", "abre el caso CYBERTEC", "como esta mi caso",
                         "conclusiones del caso", "cuantos casos tengo"):
            with self.subTest(pregunta=pregunta):
                self.assertFalse(asistente.pide_caso_nuevo(pregunta))

    def test_el_caso_generado_se_puede_registrar(self):
        from ..models import Caso
        from ..servicios import generador

        Caso.objects.all().delete()
        generado = generador.generar(semilla=4)
        respuesta = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": generado.enunciado}),
            content_type="application/json",
        )
        datos = respuesta.json()
        self.assertEqual(datos["guardados"], 8)
        self.assertEqual(datos["errores"], [])
        balance = construir_balance_comprobacion(Caso.objects.get().a_dominio())
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, generado.total_debe)


class LaEmpresaQueSeCreaEnElEnunciadoTest(TestCase):
    """El enunciado que dejaron "para los tres primeros grupos", tal cual."""

    ENUNCIADO = (
        "PARA LOS TRES PRIMEROS GRUPOS\n"
        "10/10/2026 Se crea una empresa con 100,000 al contado y 100,000 en maquinas.\n"
        "15/10/2026 Se compra 50,000 de mercaderia al credito de 15 dias.\n"
        "20/10/2026 SE realiza una venta por 100,000 soles (60% credito y 40% al contado)\n"
        "25/10/2026 Se pagan gastos operativos por 50,000 soles al contado.\n"
        "En el inventario se observa un saldo final de 25,000 soles al cierre del mes."
    )

    def _montos(self, lectura):
        return [
            {l.cuenta.nombre: (l.debe, l.haber) for l in asiento.lineas}
            for asiento in lectura.asientos
        ]

    def _comprobar(self, lectura):
        self.assertEqual(lectura.problemas, [])
        self.assertEqual(len(lectura.asientos), 6)
        suscripcion, aporte, compra, venta, gasto, costo = self._montos(lectura)
        cero = Decimal("0.00")

        # La constitución va en dos: los socios suscriben y después aportan.
        self.assertEqual(suscripcion["Cuentas por Cobrar a Socios"],
                         (Decimal("200000.00"), cero))
        self.assertEqual(suscripcion["Capital"], (cero, Decimal("200000.00")))
        self.assertEqual(aporte["Caja"], (Decimal("100000"), cero))
        self.assertEqual(aporte["Maquinaria y Equipo"], (Decimal("100000"), cero))
        self.assertEqual(aporte["Cuentas por Cobrar a Socios"], (cero, Decimal("200000.00")))

        self.assertEqual(compra["Mercaderías"], (Decimal("50000"), cero))
        self.assertEqual(compra["Proveedores"], (cero, Decimal("50000.00")))

        self.assertEqual(venta["Caja"], (Decimal("40000.00"), cero))
        self.assertEqual(venta["Clientes"], (Decimal("60000.00"), cero))
        self.assertEqual(venta["Ventas"], (cero, Decimal("100000")))

        self.assertEqual(gasto["Gastos Operativos"], (Decimal("50000"), cero))
        self.assertEqual(gasto["Caja"], (cero, Decimal("50000.00")))

        self.assertEqual(costo["Costo de Ventas"], (Decimal("25000.00"), cero))
        self.assertEqual(costo["Mercaderías"], (cero, Decimal("25000.00")))
        self.assertEqual(lectura.asientos[5].fecha.isoformat(), "2026-10-31")

    def test_resuelve_las_cinco_operaciones_en_seis_asientos(self):
        self._comprobar(enunciados.leer(self.ENUNCIADO, enunciados.CASO_VACIO))

    def test_pegado_en_una_sola_linea_tambien(self):
        """Desde el celular el texto llega a veces con las líneas juntas."""
        texto = " ".join(self.ENUNCIADO.splitlines())
        self._comprobar(enunciados.leer(texto, enunciados.CASO_VACIO))

    def test_copiado_de_una_cita_con_signos_mayor_que(self):
        """Así llegó desde el celular: "> " entre operación y operación."""
        en_una_linea = "Nombre: tres primeros grupos > " + " > ".join(
            self.ENUNCIADO.splitlines()[1:]
        )
        self._comprobar(enunciados.leer(en_una_linea, enunciados.CASO_VACIO))
        por_lineas = "\n".join("> " + l for l in self.ENUNCIADO.splitlines())
        self._comprobar(enunciados.leer(por_lineas, enunciados.CASO_VACIO))

    def test_con_otro_caso_abierto_lo_registra_aparte(self):
        from ..datos.casos_demo import LOS_ANDES
        from ..models import Caso

        andes = crear_caso_demo(LOS_ANDES)
        antes = andes.asientos.count()
        self.client.post(reverse("caso_abrir", args=[andes.pk]))
        datos = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": self.ENUNCIADO}),
            content_type="application/json",
        ).json()

        self.assertEqual(datos["guardados"], 6)
        self.assertEqual(datos["errores"], [])
        self.assertEqual(andes.asientos.count(), antes)  # Los Andes, intacto
        nuevo = Caso.objects.exclude(pk=andes.pk).get()
        self.assertEqual(nuevo.periodo_fin.isoformat(), "2026-10-31")
        balance = construir_balance_comprobacion(nuevo.a_dominio())
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("625000.00"))

    def test_el_aviso_dice_que_es_una_empresa_nueva(self):
        from ..datos.casos_demo import LOS_ANDES
        from ..servicios import asistente

        andes = crear_caso_demo(LOS_ANDES)
        respuesta = asistente.responder(self.ENUNCIADO, andes.a_dominio())
        self.assertIn("crea una empresa nueva", respuesta)
        self.assertNotIn("no la reconocí", respuesta)

    def test_con_n_antes_del_importe_no_lo_pierde(self):
        """La "n" de "con 100,000" no es un "N.º" de letra."""
        self.assertEqual(enunciados._importes("con 100,000 al contado"), [Decimal("100000")])
        self.assertEqual(enunciados._importes("letras N.º 101 y 102 por S/ 5,000"),
                         [Decimal("5000")])


class PlanillaServiciosYDepreciacionTest(TestCase):
    """El segundo enunciado: compra mitad al contado, un gasto que se paga el
    mes siguiente y la depreciación del vehículo al cierre."""

    ENUNCIADO = (
        'Aquí tienes la transcripción del texto que aparece en el archivo "1000346188.jpg":\n'
        " * 01/10/2026 Se crea una empresa con 200,000 al contado y 100,000 con un vehiculo\n"
        " * 06/10/2026 Se compra 100,000 de mercaderia 50% contado y 50% pagadero en 15 "
        "dias de credito.\n"
        " * 11/10/2026 Se realiza una venta por 200,000 soles (60% credito y 40% al contado).\n"
        " * 16/10/2026 Se pagan gastos de planilla por 50,000 soles al contado\n"
        " * y registran gastos del mes de servicios por 10,000 pagaderos el siguiente mes.\n"
        " * En el inventario se observa un saldo final de 50,000 soles al cierre del mes.\n"
        " * La depreciación es de 10% anual. Debe provisionarse al cierre de mes."
    )

    def _comprobar(self, lectura):
        self.assertEqual(lectura.problemas, [])
        self.assertEqual(len(lectura.asientos), 8)
        montos = [
            {l.cuenta.nombre: (l.debe, l.haber) for l in a.lineas} for a in lectura.asientos
        ]
        cero = Decimal("0.00")
        self.assertEqual(montos.pop(0)["Capital"], (cero, Decimal("300000.00")))  # suscripción
        self.assertEqual(montos[0]["Vehículos"], (Decimal("100000"), cero))
        self.assertEqual(montos[0]["Cuentas por Cobrar a Socios"], (cero, Decimal("300000.00")))
        self.assertEqual(montos[1]["Caja"], (cero, Decimal("50000.00")))
        self.assertEqual(montos[1]["Proveedores"], (cero, Decimal("50000.00")))
        self.assertEqual(montos[3]["Gastos de Personal"], (Decimal("50000"), cero))
        self.assertEqual(montos[4]["Gastos de Servicios"], (Decimal("10000"), cero))
        self.assertEqual(montos[4]["Cuentas por Pagar Diversas"], (cero, Decimal("10000.00")))
        self.assertEqual(montos[5]["Costo de Ventas"], (Decimal("50000.00"), cero))
        self.assertEqual(montos[6]["Gasto por Depreciación"], (Decimal("833.33"), cero))
        self.assertEqual(montos[6]["Depreciación Acumulada"], (cero, Decimal("833.33")))
        fechas = [a.fecha.isoformat() for a in lectura.asientos]
        self.assertEqual(fechas[:2], ["2026-10-01", "2026-10-01"])
        self.assertEqual(fechas[5], "2026-10-16")   # el mismo día que la planilla
        self.assertEqual(fechas[6:], ["2026-10-31", "2026-10-31"])

    def test_son_ocho_asientos(self):
        self._comprobar(enunciados.leer(self.ENUNCIADO, enunciados.CASO_VACIO))

    def test_en_una_sola_linea_tambien(self):
        texto = " ".join(l.strip(" *") for l in self.ENUNCIADO.splitlines())
        self._comprobar(enunciados.leer(texto, enunciados.CASO_VACIO))

    def test_registrado_los_reportes_cuadran(self):
        from ..dominio.balance_general import construir_balance_general
        from ..dominio.estado_resultados import construir_estado_resultados
        from ..models import Caso

        datos = self.client.post(
            reverse("asistente_registrar"),
            data=json.dumps({"texto": self.ENUNCIADO}),
            content_type="application/json",
        ).json()
        self.assertEqual(datos["guardados"], 8)
        self.assertEqual(datos["errores"], [])
        dominio = Caso.objects.get().a_dominio()
        self.assertEqual(construir_balance_comprobacion(dominio).total_debe,
                         Decimal("1010833.33"))
        resultados = construir_estado_resultados(dominio)
        # 200,000 - 50,000 - 50,000 - 10,000 - 833.33
        self.assertEqual(resultados.resultado_antes_impuesto, Decimal("89166.67"))
        balance = construir_balance_general(dominio)
        self.assertTrue(balance.cuadrado, balance.diferencia)

        # La depreciación acumulada es un activo en negativo: ninguna pantalla
        # ni reporte debe romperse por eso.
        for ruta in ("libro_diario", "libro_mayor", "balance_comprobacion",
                     "estado_resultados", "balance_general", "reporte", "reporte_excel"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(reverse(ruta)).status_code, 200)
        from ..forms import ReporteForm
        from ..servicios.pdf import generar_reporte_pdf

        secciones = [clave for clave, _ in ReporteForm.base_fields["secciones"].choices]
        self.assertTrue(generar_reporte_pdf(dominio, secciones, "").startswith(b"%PDF"))

    def test_dos_casos_sin_nombre_no_se_llaman_igual(self):
        from ..models import Caso

        for _ in range(2):
            self.client.post(
                reverse("asistente_registrar"),
                data=json.dumps({"texto": self.ENUNCIADO}),
                content_type="application/json",
            )
        self.assertEqual(
            sorted(Caso.objects.values_list("nombre", flat=True)),
            ["Caso del enunciado", "Caso del enunciado (2)"],
        )
