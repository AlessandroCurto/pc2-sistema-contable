"""Pruebas del motor contable con los casos de clase.

Las cifras son las mismas que da la versión en React: si una fórmula se tradujo
mal, estas pruebas lo muestran.
"""

from decimal import Decimal

from django.test import TestCase

from ..datos.casos_demo import (
    COMERCIALIZADORA_SUR,
    CYBERTEC,
    LOS_ANDES,
    METROPOLITANA,
    crear_caso_demo,
)
from ..dominio.balance_comprobacion import construir_balance_comprobacion
from ..dominio.balance_general import construir_balance_general
from ..dominio.estado_resultados import construir_estado_resultados
from ..dominio.libro_diario import FiltroDiario, construir_libro_diario
from ..dominio.libro_mayor import construir_libro_mayor
from ..dominio.numeros import redondear, son_iguales


class CybertecTest(TestCase):
    """CYBERTEC S.A.: 4 asientos, sin impuesto a la renta."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC).a_dominio()

    def test_balance_comprobacion_cuadrado(self):
        balance = construir_balance_comprobacion(self.caso)
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("100000.00"))
        self.assertEqual(balance.total_haber, Decimal("100000.00"))
        self.assertEqual(balance.total_deudor, balance.total_acreedor)

    def test_estado_resultados(self):
        estado = construir_estado_resultados(self.caso)
        self.assertEqual(estado.ventas_netas, Decimal("20000.00"))
        self.assertEqual(estado.utilidad_bruta, Decimal("10000.00"))
        self.assertEqual(estado.impuesto, Decimal("0.00"))
        self.assertEqual(estado.utilidad_neta, Decimal("10000.00"))

    def test_balance_general_cuadra(self):
        general = construir_balance_general(self.caso)
        self.assertTrue(general.cuadrado)
        self.assertEqual(general.total_activo, Decimal("60000.00"))
        self.assertEqual(general.total_pasivo_patrimonio, Decimal("60000.00"))

    def test_libro_diario_y_mayor_coinciden(self):
        diario = construir_libro_diario(self.caso)
        mayor = construir_libro_mayor(self.caso)
        self.assertEqual(diario.total_debe, Decimal("100000.00"))
        self.assertEqual(diario.total_debe, diario.total_haber)
        self.assertEqual(mayor.total_debe, diario.total_debe)
        self.assertEqual(mayor.total_haber, diario.total_haber)
        self.assertEqual(len(mayor.grupos), 4)

    def test_cada_asiento_cuadra(self):
        diario = construir_libro_diario(self.caso)
        for item in diario.asientos:
            self.assertTrue(item.cuadrado, "El asiento " + str(item.asiento.numero) + " no cuadra")

    def test_filtro_por_texto(self):
        filtro = FiltroDiario(texto="aporte")
        diario = construir_libro_diario(self.caso, filtro)
        self.assertEqual(len(diario.asientos), 1)
        self.assertIn("aporte", diario.asientos[0].asiento.glosa.lower())

    def test_filtro_por_cuenta(self):
        # El plan del caso es el PCGE: la caja es la cuenta 10.
        cuenta = next(cuenta for cuenta in self.caso.cuentas if cuenta.codigo == "10")
        diario = construir_libro_diario(self.caso, FiltroDiario(cuenta_id=cuenta.id))
        self.assertTrue(diario.asientos)
        for item in diario.asientos:
            codigos = [fila.cuenta.codigo for fila in item.filas if fila.cuenta]
            self.assertIn("10", codigos)


class MetropolitanaTest(TestCase):
    """Comercializadora Metropolitana: 8 asientos, impuesto del 30%."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(METROPOLITANA).a_dominio()

    def test_balance_comprobacion_cuadrado(self):
        balance = construir_balance_comprobacion(self.caso)
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("9168776.00"))

    def test_impuesto_del_treinta_por_ciento(self):
        estado = construir_estado_resultados(self.caso)
        self.assertEqual(estado.tasa_impuesto, Decimal("30.00"))
        esperado = redondear(estado.resultado_antes_impuesto * Decimal("30") / Decimal("100"))
        self.assertEqual(estado.impuesto, esperado)
        self.assertEqual(
            estado.utilidad_neta, estado.resultado_antes_impuesto - estado.impuesto
        )
        self.assertEqual(estado.utilidad_neta, Decimal("105016.80"))

    def test_balance_general_cuadra(self):
        general = construir_balance_general(self.caso)
        self.assertTrue(general.cuadrado)
        self.assertEqual(general.total_activo, Decimal("7126024.00"))
        self.assertTrue(son_iguales(general.total_activo, general.total_pasivo_patrimonio))

    def test_el_patrimonio_muestra_el_resultado_antes_de_impuesto(self):
        """El caso viene con el impuesto sin afectar al patrimonio, igual que la version web.

        Con la casilla de Configuracion marcada, el resultado del ejercicio
        pasaria a ser la utilidad neta.
        """
        estado = construir_estado_resultados(self.caso)
        general = construir_balance_general(self.caso)
        self.assertFalse(general.resultado_neto_de_impuesto)
        self.assertEqual(general.resultado_ejercicio, estado.resultado_antes_impuesto)

    def test_con_la_casilla_marcada_el_resultado_es_neto(self):
        from dataclasses import replace

        caso = replace(
            self.caso, empresa=replace(self.caso.empresa, impuesto_afecta_patrimonio=True)
        )
        estado = construir_estado_resultados(caso)
        general = construir_balance_general(caso)
        self.assertTrue(general.resultado_neto_de_impuesto)
        self.assertEqual(general.resultado_ejercicio, estado.utilidad_neta)
        self.assertEqual(general.impuesto_por_pagar, Decimal("45007.20"))
        self.assertTrue(general.cuadrado)


class ComercializadoraSurTest(TestCase):
    """Comercializadora del Sur S.A.C.: IGV del 18% e impuesto a la renta del 29.5%."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR).a_dominio()

    def test_balance_comprobacion_cuadrado(self):
        balance = construir_balance_comprobacion(self.caso)
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("9170697.63"))

    def test_costo_de_ventas_por_diferencia_de_inventarios(self):
        mayor = {
            item.cuenta.codigo: item
            for grupo in construir_libro_mayor(self.caso).grupos
            for item in grupo.cuentas
        }
        self.assertEqual(mayor["105"].saldo, Decimal("690360.00"))

    def test_estado_resultados(self):
        estado = construir_estado_resultados(self.caso)
        self.assertEqual(estado.resultado_antes_impuesto, Decimal("142902.37"))
        self.assertEqual(estado.impuesto, Decimal("42156.20"))
        self.assertEqual(estado.utilidad_neta, Decimal("100746.17"))

    def test_balance_general_cuadra(self):
        general = construir_balance_general(self.caso)
        self.assertTrue(general.cuadrado)
        self.assertEqual(general.total_activo, Decimal("7114902.37"))

    def test_el_impuesto_queda_como_pasivo_y_el_patrimonio_lleva_la_utilidad_neta(self):
        general = construir_balance_general(self.caso)
        pasivos = {d.cuenta.nombre: d.monto for d in general.pasivo_corriente.cuentas}
        self.assertEqual(pasivos["Impuesto a la renta por pagar"], Decimal("42156.20"))
        self.assertEqual(general.total_pasivo, Decimal("1214156.20"))
        self.assertEqual(general.resultado_ejercicio, Decimal("100746.17"))
        self.assertEqual(general.total_patrimonio, Decimal("5900746.17"))


class FerreteriaLosAndesTest(TestCase):
    """Ferretería Los Andes S.R.L.: compras y ventas al contado y al crédito,
    sueldos y cobranza. Las cifras están calculadas a mano una por una."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(LOS_ANDES).a_dominio()

    def test_cada_asiento_cuadra(self):
        from ..dominio.libro_diario import FiltroDiario, construir_libro_diario

        for item in construir_libro_diario(self.caso, FiltroDiario()).asientos:
            self.assertTrue(item.cuadrado, item.asiento.glosa)

    def test_balance_de_comprobacion(self):
        balance = construir_balance_comprobacion(self.caso)
        self.assertTrue(balance.cuadrado)
        self.assertEqual(balance.total_debe, Decimal("4891400.00"))
        self.assertEqual(balance.total_haber, Decimal("4891400.00"))

    def test_los_saldos_del_mayor(self):
        saldos = {
            item.cuenta.codigo: item.saldo
            for grupo in construir_libro_mayor(self.caso).grupos
            for item in grupo.cuentas
        }
        esperados = {
            "101": "1195000",   # caja: 900,000 + 295,000 de la venta al contado
            "102": "956000",    # banco: 1,500,000 - 354,000 - 90,000 + 200,000 - 300,000
            "103": "332400",    # clientes: 320,000 + 212,400 - 200,000
            "105": "540000",    # mercaderías: 480,000 + 300,000 - 240,000
            "106": "54000",     # IGV crédito fiscal de la compra
            "201": "200000",    # proveedores: 500,000 - 60%
            "203": "77400",     # IGV débito: 45,000 + 32,400
            "301": "2700000",
            "401": "430000",    # 250,000 + 180,000
            "502": "240000",
            "505": "90000",
        }
        for codigo, esperado in esperados.items():
            self.assertEqual(saldos[codigo], Decimal(esperado), "cuenta " + codigo)

    def test_estado_de_resultados(self):
        estado = construir_estado_resultados(self.caso)
        self.assertEqual(estado.ventas_netas, Decimal("430000.00"))
        self.assertEqual(estado.costo_ventas, Decimal("240000.00"))
        self.assertEqual(estado.utilidad_bruta, Decimal("190000.00"))
        self.assertEqual(estado.gasto_administracion, Decimal("90000.00"))
        self.assertEqual(estado.resultado_antes_impuesto, Decimal("100000.00"))
        self.assertEqual(estado.tasa_impuesto, Decimal("29.50"))
        self.assertEqual(estado.impuesto, Decimal("29500.00"))
        self.assertEqual(estado.utilidad_neta, Decimal("70500.00"))

    def test_balance_general(self):
        general = construir_balance_general(self.caso)
        self.assertTrue(general.cuadrado)
        self.assertEqual(general.total_activo, Decimal("3077400.00"))
        self.assertEqual(general.total_pasivo, Decimal("306900.00"))
        self.assertEqual(general.impuesto_por_pagar, Decimal("29500.00"))
        self.assertEqual(general.total_patrimonio, Decimal("2770500.00"))
        self.assertTrue(son_iguales(general.total_activo, general.total_pasivo_patrimonio))

    def test_el_patrimonio_lleva_la_utilidad_neta(self):
        estado = construir_estado_resultados(self.caso)
        general = construir_balance_general(self.caso)
        self.assertTrue(general.resultado_neto_de_impuesto)
        self.assertEqual(general.resultado_ejercicio, estado.utilidad_neta)


class CobrosConChequeTest(TestCase):
    """Un cheque recibido se deposita: entra al banco, no a la caja."""

    def test_en_los_casos_de_ejemplo(self):
        from ..datos.casos_demo import PLANTILLAS_CASO

        for plantilla in PLANTILLAS_CASO:
            for asiento in plantilla.asientos:
                if "cheque" not in asiento.glosa.lower():
                    continue
                for linea in asiento.lineas:
                    with self.subTest(caso=plantilla.id, glosa=asiento.glosa[:40]):
                        self.assertNotEqual(
                            linea.codigo, "101",
                            "un movimiento con cheque no puede tocar Caja",
                        )
                        self.assertNotEqual(linea.codigo, "10", "idem en el PCGE")

    def test_los_saldos_de_caja_y_banco_del_caso_del_sur(self):
        caso = crear_caso_demo(COMERCIALIZADORA_SUR).a_dominio()
        saldos = {
            item.cuenta.codigo: item.saldo
            for grupo in construir_libro_mayor(caso).grupos
            for item in grupo.cuentas
        }
        self.assertEqual(saldos["101"], Decimal("2688800"))   # caja
        self.assertEqual(saldos["102"], Decimal("2841600"))   # banco
        # El total no cambia: solo se movió de una cuenta a la otra.
        self.assertEqual(saldos["101"] + saldos["102"], Decimal("5530400"))


class LosCincoReportesNoPuedenDiscrepar(TestCase):
    """Los cinco reportes salen de los mismos asientos, no de copias guardadas.

    Se afirmó que el Libro Mayor podía quedar en una versión vieja mientras el
    Balance de Comprobación tenía otra. No es posible: nada se almacena
    calculado. Esta prueba lo deja asentado para los cuatro casos de ejemplo.
    """

    def _casos(self):
        from ..datos.casos_demo import PLANTILLAS_CASO

        for plantilla in PLANTILLAS_CASO:
            yield plantilla.id, crear_caso_demo(plantilla).a_dominio()

    def test_el_mayor_y_el_balance_de_comprobacion_dan_los_mismos_saldos(self):
        for nombre, caso in self._casos():
            mayor = {
                item.cuenta.codigo: item.saldo
                for grupo in construir_libro_mayor(caso).grupos
                for item in grupo.cuentas
            }
            for fila in construir_balance_comprobacion(caso).filas:
                with self.subTest(caso=nombre, cuenta=fila.cuenta.codigo):
                    saldo = fila.saldo_deudor or fila.saldo_acreedor
                    self.assertEqual(mayor[fila.cuenta.codigo], saldo)

    def test_el_balance_general_usa_esos_mismos_saldos(self):
        for nombre, caso in self._casos():
            mayor = {
                item.cuenta.codigo: item.saldo
                for grupo in construir_libro_mayor(caso).grupos
                for item in grupo.cuentas
            }
            general = construir_balance_general(caso)
            bloques = (general.activo_corriente, general.activo_no_corriente,
                       general.pasivo_corriente, general.pasivo_no_corriente,
                       general.patrimonio)
            for bloque in bloques:
                for detalle in bloque.cuentas:
                    codigo = detalle.cuenta.codigo
                    if codigo not in mayor:
                        continue  # el impuesto por pagar no nace de un asiento
                    with self.subTest(caso=nombre, cuenta=codigo):
                        self.assertEqual(detalle.monto, mayor[codigo])

    def test_el_diario_suma_lo_mismo_que_el_balance_de_comprobacion(self):
        from ..dominio.libro_diario import FiltroDiario, construir_libro_diario

        for nombre, caso in self._casos():
            with self.subTest(caso=nombre):
                diario = construir_libro_diario(caso, FiltroDiario())
                balance = construir_balance_comprobacion(caso)
                self.assertEqual(diario.total_debe, balance.total_debe)
                self.assertEqual(diario.total_haber, balance.total_haber)
