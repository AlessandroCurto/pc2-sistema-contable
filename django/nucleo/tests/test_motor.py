"""Pruebas del motor contable con los casos de clase.

Las cifras son las mismas que da la versión en React: si una fórmula se tradujo
mal, estas pruebas lo muestran.
"""

from decimal import Decimal

from django.test import TestCase

from ..datos.casos_demo import COMERCIALIZADORA_SUR, CYBERTEC, METROPOLITANA, crear_caso_demo
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
