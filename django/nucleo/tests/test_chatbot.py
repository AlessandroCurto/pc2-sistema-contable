"""Pruebas del asistente: el contexto del caso, el filtro de mensajes y la vista.

No llaman a la API: la respuesta del modelo se reemplaza por una falsa.
"""

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from django.test import TestCase
from django.urls import reverse

from ..datos.casos_demo import COMERCIALIZADORA_SUR, CYBERTEC, crear_caso_demo
from ..servicios import asistente
from ..servicios import chatbot as servicio
from ..views import _mensajes_validos


def _respuesta_falsa(*_args, **_kwargs):
    yield "Respuesta "
    yield "de prueba."


class ContextoDelCasoTest(TestCase):
    """Lo que el asistente ve del caso abierto."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)

    def test_sin_caso_lo_dice(self):
        texto = servicio._contexto_del_caso(None)
        self.assertIn("no tiene ningún caso abierto", texto)

    def test_incluye_empresa_cuentas_y_asientos(self):
        texto = servicio._contexto_del_caso(self.caso.a_dominio())
        self.assertIn("Comercializadora del Sur S.A.C.", texto)
        self.assertIn("20100000003", texto)
        self.assertIn("IGV Crédito Fiscal", texto)
        self.assertIn("Adelco Ltda", texto)
        self.assertIn("29.5%", texto)

    def test_incluye_las_cifras_ya_calculadas(self):
        texto = servicio._contexto_del_caso(self.caso.a_dominio())
        self.assertIn("9,170,697.63", texto)   # total del Debe
        self.assertIn("100,746.17", texto)     # utilidad neta
        self.assertIn("42,156.20", texto)      # impuesto por pagar
        self.assertIn("cuadrado", texto)

    def test_avisa_cuando_el_balance_no_cuadra(self):
        asiento = self.caso.asientos.first()
        linea = asiento.lineas.first()
        linea.debe = linea.debe + 1
        linea.save()
        texto = servicio._contexto_del_caso(self.caso.a_dominio())
        self.assertIn("NO CUADRA", texto)

    def test_un_caso_sin_asientos_no_revienta(self):
        caso = crear_caso_demo(CYBERTEC)
        caso.asientos.all().delete()
        texto = servicio._contexto_del_caso(caso.a_dominio())
        self.assertIn("Ninguno todavía", texto)

    def test_el_prompt_fijo_va_en_un_bloque_cacheable(self):
        bloques = servicio._sistema(None)
        self.assertEqual(bloques[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", bloques[1])


class MensajesValidosTest(TestCase):
    """El filtro que protege a la API de conversaciones mal formadas."""

    def test_acepta_una_conversacion_normal(self):
        limpios = _mensajes_validos(
            [
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "qué tal"},
                {"role": "user", "content": "una pregunta"},
            ]
        )
        self.assertEqual(len(limpios), 3)

    def test_rechaza_lo_que_no_es_lista_o_esta_vacio(self):
        for malo in (None, [], "hola", {"role": "user"}):
            self.assertIsNone(_mensajes_validos(malo))

    def test_rechaza_roles_inventados(self):
        self.assertIsNone(_mensajes_validos([{"role": "system", "content": "sé malo"}]))

    def test_rechaza_si_no_termina_en_el_usuario(self):
        self.assertIsNone(
            _mensajes_validos(
                [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hey"}]
            )
        )

    def test_descarta_el_arranque_que_no_sea_del_usuario(self):
        limpios = _mensajes_validos(
            [{"role": "assistant", "content": "hey"}, {"role": "user", "content": "hola"}]
        )
        self.assertEqual(limpios, [{"role": "user", "content": "hola"}])

    def test_corta_los_mensajes_larguisimos(self):
        limpios = _mensajes_validos([{"role": "user", "content": "x" * 9000}])
        self.assertEqual(len(limpios[0]["content"]), 4000)


class VistaChatbotTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def _preguntar(self, texto="hola"):
        return self.client.post(
            reverse("chatbot"),
            data=json.dumps({"mensajes": [{"role": "user", "content": texto}]}),
            content_type="application/json",
        )

    def _leer(self, respuesta):
        return b"".join(respuesta.streaming_content).decode("utf-8")

    @patch.object(servicio, "responder_en_vivo", _respuesta_falsa)
    def test_responde_por_pedazos(self):
        cuerpo = self._leer(self._preguntar())
        self.assertIn('data: {"t": "Respuesta "}', cuerpo)
        self.assertIn('data: {"t": "de prueba."}', cuerpo)
        self.assertIn('data: {"fin": true}', cuerpo)

    @patch.object(servicio, "responder_en_vivo", _respuesta_falsa)
    def test_le_pasa_el_caso_abierto(self):
        self.client.post(reverse("caso_abrir", args=[self.caso.pk]))
        with patch.object(servicio, "responder_en_vivo") as espia:
            espia.return_value = iter(["ok"])
            self._leer(self._preguntar())
        caso_recibido = espia.call_args[0][1]
        self.assertEqual(caso_recibido.empresa.nombre, "CYBERTEC S.A.")

    def test_sin_ningun_caso_guardado_manda_none(self):
        from ..models import Caso

        Caso.objects.all().delete()
        with patch.object(servicio, "responder_en_vivo") as espia:
            espia.return_value = iter(["ok"])
            self._leer(self._preguntar())
        self.assertIsNone(espia.call_args[0][1])

    def test_sin_clave_avisa_en_espanol(self):
        def sin_clave(*_a, **_k):
            raise servicio.ChatbotNoConfigurado("falta la clave")
            yield  # pragma: no cover

        with patch.object(servicio, "responder_en_vivo", sin_clave):
            cuerpo = self._leer(self._preguntar())
        self.assertIn("falta la clave", cuerpo)
        self.assertIn('"fin": true', cuerpo)

    def test_un_error_de_la_api_no_filtra_detalles(self):
        def revienta(*_a, **_k):
            raise RuntimeError("Invalid API key sk-ant-secreta")
            yield  # pragma: no cover

        with patch.object(servicio, "responder_en_vivo", revienta):
            cuerpo = self._leer(self._preguntar())
        self.assertNotIn("sk-ant", cuerpo)
        self.assertIn("no está disponible", cuerpo)

    def test_el_get_no_sirve(self):
        self.assertEqual(self.client.get(reverse("chatbot")).status_code, 405)

    def test_json_roto(self):
        respuesta = self.client.post(
            reverse("chatbot"), data="{no es json", content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_conversacion_incompleta(self):
        respuesta = self.client.post(
            reverse("chatbot"), data=json.dumps({"mensajes": []}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 400)

    @patch.object(servicio, "responder_en_vivo", _respuesta_falsa)
    def test_hay_un_tope_de_preguntas_por_hora(self):
        from ..views import CHAT_TOPE

        for _ in range(CHAT_TOPE):
            self._leer(self._preguntar())
        respuesta = self._preguntar()
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("límite", respuesta.json()["error"])


class PaginaConElAsistenteTest(TestCase):
    def test_la_pagina_trae_el_token_y_los_archivos(self):
        respuesta = self.client.get(reverse("casos"))
        self.assertContains(respuesta, 'id="chat-datos"')
        self.assertContains(respuesta, "chatbot.js")
        self.assertContains(respuesta, "chatbot.css")


class AsistenteLocalTest(TestCase):
    """El asistente que responde sin API: fichas, revisiones en vivo y cuentas."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)

    def _responder(self, pregunta, caso=True):
        dominio = self.caso.a_dominio() if caso is True else caso
        return asistente.responder(pregunta, dominio)

    # ---- fichas de contenido

    def test_responde_sobre_el_sistema(self):
        self.assertIn("Registrar Asiento", self._responder("como registro un asiento"))
        self.assertIn("plantilla", self._responder("como importo desde excel"))
        self.assertIn("PDF", self._responder("como descargo el pdf"))

    def test_responde_teoria(self):
        self.assertIn("partida doble", self._responder("que es la partida doble").lower())
        self.assertIn("Deudora", self._responder("que va al debe y que al haber"))
        self.assertIn("847,457.63", self._responder("como se calcula el igv"))

    def test_no_le_afectan_las_tildes_ni_las_mayusculas(self):
        con = self._responder("¿CÓMO REGISTRO UN ASIENTO?")
        sin = self._responder("como registro un asiento")
        self.assertEqual(con, sin)

    def test_cuando_no_entiende_lo_dice_y_no_inventa(self):
        respuesta = self._responder("cual es la capital de francia")
        self.assertIn("No estoy seguro", respuesta)

    # ---- revisiones en vivo

    def test_el_resumen_trae_las_cifras_reales(self):
        respuesta = self._responder("como esta mi caso")
        self.assertIn("Comercializadora del Sur S.A.C.", respuesta)
        self.assertIn("100,746.17", respuesta)
        self.assertIn("7,114,902.37", respuesta)

    def test_dice_que_un_caso_sano_no_tiene_descuadres(self):
        self.assertIn("no encontré ningún descuadre", self._responder("por que no cuadra"))

    def test_senala_el_asiento_descuadrado(self):
        asiento = self.caso.asientos.order_by("numero").first()
        linea = asiento.lineas.first()
        linea.debe = linea.debe + 500
        linea.save()
        respuesta = self._responder("por que no me cuadra")
        self.assertIn("no cuadran", respuesta)
        self.assertIn(str(asiento.numero), respuesta)
        self.assertIn("500.00", respuesta)

    def test_suma_el_igv_del_caso(self):
        respuesta = self._responder("cuanto igv tengo")
        self.assertIn("152,542.37", respuesta)   # crédito fiscal
        self.assertIn("72,000.00", respuesta)    # débito fiscal
        self.assertIn("80,542.37", respuesta)    # saldo a favor

    def test_lista_los_asientos(self):
        respuesta = self._responder("que asientos tengo")
        self.assertIn("8 asientos", respuesta)
        self.assertIn("Adelco", respuesta)

    def test_sin_caso_pide_abrir_uno(self):
        for pregunta in ("como esta mi caso", "por que no cuadra", "cuanto igv tengo"):
            self.assertIn("ningún caso abierto", self._responder(pregunta, caso=None))

    # ---- cuentas con el monto de la pregunta

    def test_calcula_el_igv_incluido(self):
        respuesta = self._responder("cuanto es el igv de 1,000,000 incluido")
        self.assertIn("847,457.63", respuesta)
        self.assertIn("152,542.37", respuesta)

    def test_calcula_el_igv_sobre_la_base(self):
        respuesta = self._responder("cuanto es el igv de 400000 mas igv")
        self.assertIn("72,000.00", respuesta)
        self.assertIn("472,000.00", respuesta)

    # ---- enlace con la vista

    def test_fue_entendida_distingue(self):
        self.assertTrue(asistente.fue_entendida("como registro un asiento"))
        self.assertFalse(asistente.fue_entendida("cual es la capital de francia"))
        self.assertFalse(asistente.fue_entendida(""))


class SinClaveDeApiTest(TestCase):
    """Sin ANTHROPIC_API_KEY el asistente responde igual, con lo local."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def test_responde_sin_clave(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            respuesta = self.client.post(
                reverse("chatbot"),
                data=json.dumps(
                    {"mensajes": [{"role": "user", "content": "como registro un asiento"}]}
                ),
                content_type="application/json",
            )
            cuerpo = b"".join(respuesta.streaming_content).decode("utf-8")
        self.assertIn("Registrar Asiento", cuerpo)
        self.assertNotIn("no está configurado", cuerpo)
        self.assertIn('"fin": true', cuerpo)

    def test_sin_clave_una_pregunta_rara_no_llama_a_la_api(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            with patch.object(servicio, "_responder_con_api") as api:
                respuesta = self.client.post(
                    reverse("chatbot"),
                    data=json.dumps(
                        {"mensajes": [{"role": "user", "content": "quien gano el mundial"}]}
                    ),
                    content_type="application/json",
                )
                b"".join(respuesta.streaming_content)
            api.assert_not_called()


class TopeDiarioGlobalTest(TestCase):
    """El sitio es público: sin tope global cualquiera podría gastar el saldo."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(CYBERTEC)

    def _preguntar_raro(self):
        """Una pregunta que lo local no entiende, o sea candidata a la API."""
        return self.client.post(
            reverse("chatbot"),
            data=json.dumps(
                {"mensajes": [{"role": "user", "content": "quien gano el mundial del 86"}]}
            ),
            content_type="application/json",
        )

    def _leer(self, respuesta):
        return b"".join(respuesta.streaming_content).decode("utf-8")

    def test_cuenta_solo_lo_que_llega_a_la_api(self):
        from ..models import UsoAsistente

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-de-prueba"}, clear=False):
            with patch.object(servicio, "_responder_con_api") as api:
                api.return_value = iter(["respuesta del modelo"])
                self._leer(self._preguntar_raro())
        self.assertEqual(UsoAsistente.objects.get().consultas, 1)

    def test_una_pregunta_que_lo_local_entiende_no_gasta(self):
        from ..models import UsoAsistente

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-de-prueba"}, clear=False):
            with patch.object(servicio, "_responder_con_api") as api:
                self.client.post(
                    reverse("chatbot"),
                    data=json.dumps(
                        {"mensajes": [{"role": "user", "content": "como registro un asiento"}]}
                    ),
                    content_type="application/json",
                )
                api.assert_not_called()
        self.assertFalse(UsoAsistente.objects.exists())

    def test_sin_clave_no_cuenta_nada(self):
        from ..models import UsoAsistente

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            self._leer(self._preguntar_raro())
        self.assertFalse(UsoAsistente.objects.exists())

    def test_agotado_el_cupo_sigue_respondiendo_pero_gratis(self):
        from ..models import UsoAsistente
        from ..views import CHAT_TOPE_DIARIO

        UsoAsistente.objects.create(
            fecha=timezone.localdate(), consultas=CHAT_TOPE_DIARIO
        )
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-de-prueba"}, clear=False):
            with patch.object(servicio, "_responder_con_api") as api:
                cuerpo = self._leer(self._preguntar_raro())
                api.assert_not_called()
        # No se rompe: cae en la respuesta local y el contador no sube.
        self.assertIn("No estoy seguro", cuerpo)
        self.assertEqual(UsoAsistente.objects.get().consultas, CHAT_TOPE_DIARIO)

    def test_el_tope_se_puede_apagar_del_todo(self):
        from ..models import UsoAsistente

        with patch("nucleo.views.CHAT_TOPE_DIARIO", 0):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-x"}, clear=False):
                with patch.object(servicio, "_responder_con_api") as api:
                    self._leer(self._preguntar_raro())
                    api.assert_not_called()
        self.assertFalse(UsoAsistente.objects.exists())

    def test_el_cupo_es_por_dia(self):
        from ..models import UsoAsistente
        from ..views import CHAT_TOPE_DIARIO

        ayer = timezone.localdate() - timedelta(days=1)
        UsoAsistente.objects.create(fecha=ayer, consultas=CHAT_TOPE_DIARIO)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-x"}, clear=False):
            with patch.object(servicio, "_responder_con_api") as api:
                api.return_value = iter(["ok"])
                self._leer(self._preguntar_raro())
                api.assert_called_once()
        self.assertEqual(UsoAsistente.objects.get(fecha=timezone.localdate()).consultas, 1)


class PreguntasPorUnaCifraTest(TestCase):
    """«¿Cuál es mi utilidad neta?» pide un número del caso, no una ficha.

    Antes contestaba la ficha de teoría del impuesto a la renta, cuyas cifras
    de muestra se leían como si fueran las del estudiante.
    """

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.dominio = cls.caso.a_dominio()

    def _responder(self, pregunta):
        return asistente.responder(pregunta, self.dominio)

    def test_da_la_utilidad_neta_del_caso(self):
        respuesta = self._responder("¿Cuál es mi utilidad neta?")
        self.assertIn("100,746.17", respuesta)
        self.assertIn("Comercializadora del Sur", respuesta)
        self.assertNotIn("105,766.92", respuesta)   # el número de la ficha

    def test_cada_cifra_devuelve_la_suya(self):
        esperados = {
            "cuanto es mi impuesto a la renta": "42,156.20",
            "cual es mi costo de ventas": "157,097.63",
            "cuanto vendi": "400,000.00",
            "cual es mi utilidad bruta": "242,902.37",
            "cuanto es mi activo total": "7,114,902.37",
            "cuanto es mi pasivo": "1,214,156.20",
            "cuanto es mi patrimonio": "5,900,746.17",
            "cuanto es el total del debe": "9,170,697.63",
            "cuanto gane este mes": "100,746.17",
        }
        for pregunta, esperado in esperados.items():
            with self.subTest(pregunta=pregunta):
                self.assertIn(esperado, self._responder(pregunta))

    def test_el_costo_de_ventas_no_se_confunde_con_las_ventas(self):
        """«costo de ventas» contiene «ventas»: gana la cifra más específica."""
        respuesta = self._responder("cual es mi costo de ventas")
        self.assertIn("**Costo de ventas**", respuesta)

    def test_preguntar_la_teoria_sigue_dando_la_ficha(self):
        for pregunta in ("como se calcula el impuesto a la renta",
                         "que es la utilidad neta",
                         "como se calcula el costo de ventas"):
            with self.subTest(pregunta=pregunta):
                self.assertIsNone(asistente.cifra_pedida(pregunta))

    def test_la_ficha_avisa_que_sus_numeros_son_de_muestra(self):
        ficha = next(f for f in asistente.FICHAS if f.clave == "impuesto-renta")
        self.assertIn("no son las tuyas", ficha.texto)

    def test_sin_caso_pide_abrir_uno(self):
        self.assertIn("ningún caso abierto", asistente.responder("mi utilidad neta", None))

    def test_sin_caso_una_pregunta_de_teoria_sigue_llegando_a_su_ficha(self):
        """«impuesto a la renta» a secas es teoría, no una consulta del caso."""
        respuesta = asistente.responder("impuesto a la renta", None)
        self.assertIn("tercera categoría", respuesta)


class AbrirOtroCasoTest(TestCase):
    """«Abre el caso X» cambia de caso sin salir del chat."""

    @classmethod
    def setUpTestData(cls):
        cls.sur = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.cybertec = crear_caso_demo(CYBERTEC)

    def _pedir(self, texto):
        respuesta = self.client.post(
            reverse("chatbot"),
            data=json.dumps({"mensajes": [{"role": "user", "content": texto}]}),
            content_type="application/json",
        )
        return b"".join(respuesta.streaming_content).decode("utf-8")

    def test_reconoce_la_intencion(self):
        for frase, esperado in [
            ("abre el caso CYBERTEC", "cybertec"),
            ("quiero que abras el caso Comercializadora del Sur", "comercializadora del sur"),
            ("ábreme el caso CYBERTEC S.A.", "cybertec s.a"),
            ("cambia al caso CYBERTEC", "cybertec"),
            ("carga el caso Los Andes", "los andes"),
        ]:
            with self.subTest(frase=frase):
                self.assertEqual(asistente.caso_pedido(frase), esperado)

    def test_no_confunde_otras_preguntas(self):
        for frase in ("como creo un caso nuevo", "que es la partida doble",
                      "como esta mi caso", "cuantos casos tengo", "abre un caso nuevo"):
            with self.subTest(frase=frase):
                self.assertIsNone(asistente.caso_pedido(frase))

    def test_abre_el_caso_y_pide_recargar(self):
        self.client.post(reverse("caso_abrir", args=[self.sur.pk]))
        cuerpo = self._pedir("abre el caso CYBERTEC")
        self.assertIn("CYBERTEC S.A.", cuerpo)
        self.assertIn('"accion": "recargar"', cuerpo)
        self.assertEqual(self.client.session["caso_activo_id"], self.cybertec.pk)

    def test_encuentra_el_caso_aunque_el_nombre_venga_a_medias(self):
        self.client.post(reverse("caso_abrir", args=[self.cybertec.pk]))
        self._pedir("quiero que abras el caso comercializadora del sur")
        self.assertEqual(self.client.session["caso_activo_id"], self.sur.pk)

    def test_si_no_existe_lo_dice_y_lista_los_que_hay(self):
        cuerpo = self._pedir("abre el caso Panaderia La Esperanza")
        self.assertIn("No encontré", cuerpo)
        self.assertIn("CYBERTEC S.A.", cuerpo)
        self.assertNotIn("recargar", cuerpo)

    def test_no_cambia_de_caso_si_no_encuentra(self):
        self.client.post(reverse("caso_abrir", args=[self.sur.pk]))
        self._pedir("abre el caso Panaderia La Esperanza")
        self.assertEqual(self.client.session["caso_activo_id"], self.sur.pk)


class MuluniTest(TestCase):
    def test_la_pagina_entrega_el_avatar(self):
        respuesta = self.client.get(reverse("casos"))
        self.assertContains(respuesta, "muluni.png")
        self.assertContains(respuesta, "data-avatar")

    def test_el_chat_se_llama_muluni(self):
        from django.conf import settings

        js = (settings.BASE_DIR / "nucleo/static/nucleo/chatbot.js").read_text(encoding="utf-8")
        self.assertIn("<strong>MULUNI</strong>", js)
        self.assertNotIn("Asistente contable</strong>", js)


class VariantesDeLasPalabrasTest(TestCase):
    """Nadie escribe la palabra exacta: hay que aceptar las formas derivadas."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.dominio = cls.caso.a_dominio()

    def test_reconoce_la_misma_palabra_en_otra_forma(self):
        iguales = [
            ("tasa", "tasas"), ("asiento", "asientos"), ("cuenta", "cuentas"),
            ("calcular", "calculas"), ("calcular", "calculo"), ("registrar", "registro"),
            ("importar", "importacion"), ("letra", "letras"), ("costo", "costos"),
        ]
        for una, otra in iguales:
            with self.subTest(par=(una, otra)):
                self.assertTrue(asistente.misma_raiz(una, otra))

    def test_no_confunde_palabras_distintas(self):
        """Comparar comienzos tiene un límite: «venta» y «ventaja» lo comparten.

        Se acepta porque ninguna de esas palabras aparece en estas preguntas; lo
        que no debe pasar es que se confundan términos que sí se usan aquí.
        """
        distintas = [("pagar", "pagina"), ("caso", "casi"), ("activo", "adjetivo"),
                     ("debe", "haber"), ("compra", "cobro"), ("cuenta", "cuadre")]
        for una, otra in distintas:
            with self.subTest(par=(una, otra)):
                self.assertFalse(asistente.misma_raiz(una, otra), f"{una} / {otra}")

    def test_varias_formas_llegan_a_la_misma_ficha(self):
        esperados = {
            "como registro asientos": "Registrar un asiento",
            "quiero registrar un asiento": "Registrar un asiento",
            "el registro de asientos": "Registrar un asiento",
            "importar desde excel": "Importar asientos",
            "la importacion de excel": "Importar asientos",
            "que son las letras": "Letras de cambio",
            "la letra de cambio": "Letras de cambio",
            "las cuentas del plan": "Plan de Cuentas",
        }
        for pregunta, titulo in esperados.items():
            with self.subTest(pregunta=pregunta):
                self.assertIn(titulo, asistente.responder(pregunta, self.dominio))


class PreguntasSobreElSistemaTest(TestCase):
    """«¿Cuál es la tasa que usas?» pregunta por el sistema, no por el caso."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.dominio = cls.caso.a_dominio()

    def test_responde_por_sus_tasas(self):
        for pregunta in ("¿cuál es la tasa que usas?", "que tasa usas",
                         "con que igv trabajas", "que porcentaje de impuesto aplicas",
                         "cuantos decimales usas", "como redondeas"):
            with self.subTest(pregunta=pregunta):
                respuesta = asistente.responder(pregunta, self.dominio)
                self.assertIn("18%", respuesta)
                self.assertIn("29.5%", respuesta)

    def test_incluye_la_tasa_del_caso_abierto(self):
        respuesta = asistente.responder("que tasa usas", self.dominio)
        self.assertIn("Comercializadora del Sur", respuesta)
        self.assertIn("29.5", respuesta)

    def test_avisa_cuando_el_caso_quedo_en_cero(self):
        self.caso.tasa_impuesto_renta = 0
        self.caso.save()
        respuesta = asistente.responder("que tasa usas", self.caso.a_dominio())
        self.assertIn("Con 0% no se calcula impuesto", respuesta)

    def test_explica_como_funciona_la_pagina(self):
        for pregunta in ("como funciona la pagina", "que hace el sistema",
                         "como trabaja esto", "para que sirve esta pagina", "como se usa"):
            with self.subTest(pregunta=pregunta):
                self.assertIn("Cómo funciona", asistente.responder(pregunta, self.dominio))

    def test_distingue_el_metodo_de_la_cifra(self):
        metodo = {
            "para calcular el impuesto": "## Impuesto a la renta",
            "calcular el costo de ventas": "## Costo de ventas por diferencia",
            "el calculo del igv": "## El IGV",
        }
        for pregunta, inicio in metodo.items():
            with self.subTest(pregunta=pregunta):
                self.assertTrue(asistente.responder(pregunta, self.dominio).startswith(inicio))

        # Con "mi" delante, lo que quiere es su número.
        cifra = {
            "cual es mi costo de ventas": "157,097.63",
            "cuanto es mi impuesto a la renta": "42,156.20",
        }
        for pregunta, numero in cifra.items():
            with self.subTest(pregunta=pregunta):
                self.assertIn(numero, asistente.responder(pregunta, self.dominio))


class MuchasFormasDePreguntarTest(TestCase):
    """No hay que acertar la frase exacta: «qué IGV trabajas» vale igual que
    «con qué IGV trabajas». Esta batería cubre las formas que se usan de verdad."""

    FORMAS = {
        "Las tasas que uso": [
            "que igv trabajas", "que igv usas", "con que igv", "igv que usas", "que tasa",
            "tasa que usas", "cual tasa manejas", "con que porcentaje trabajas",
            "que impuesto aplicas", "cuantos decimales", "como redondeas", "que tasas tienes",
        ],
        "Cómo funciona": [
            "como funciona", "como trabaja la pagina", "que hace el sistema",
            "como se usa esto", "explicame el sistema",
        ],
        "Registrar un asiento": [
            "registrar asiento", "como registro", "quiero anotar un asiento",
            "crear asiento", "nuevo asiento", "el registro de asientos",
        ],
        "Importar asientos": [
            "importar excel", "subir excel", "excel", "importacion de asientos",
            "cargar desde csv", "plantilla de excel",
        ],
        "El IGV": [
            "como se calcula el igv", "calcular igv", "el igv incluido",
            "igv credito fiscal", "sacar el igv",
        ],
        "Costo de ventas": [
            "costo de ventas", "diferencia de inventarios", "existencia final",
            "calcular el costo", "como saco el costo de ventas",
        ],
        "Letras de cambio": [
            "letras de cambio", "la letra", "que son las letras", "letras por cobrar",
        ],
        "Plan de Cuentas": [
            "plan de cuentas", "agregar cuenta", "crear una cuenta", "eliminar cuenta",
            "las cuentas",
        ],
        "Descargas": ["descargar pdf", "generar pdf", "exportar a excel", "imprimir"],
        "Debe y qué al Haber": [
            "que va al debe", "debe o haber", "naturaleza de las cuentas", "cuando va al haber",
        ],
        "partida doble": ["partida doble", "la doble partida", "por que debe igual haber"],
        "ciclo contable": ["ciclo contable", "pasos para resolver", "por donde empiezo"],
    }

    @classmethod
    def setUpTestData(cls):
        cls.dominio = crear_caso_demo(COMERCIALIZADORA_SUR).a_dominio()

    def test_todas_las_formas_llegan_a_su_ficha(self):
        for esperado, preguntas in self.FORMAS.items():
            for pregunta in preguntas:
                with self.subTest(pregunta=pregunta):
                    primera = asistente.responder(pregunta, self.dominio).split("\n")[0]
                    self.assertIn(esperado.lower(), primera.lower())

    def test_una_sola_palabra_tambien_sirve(self):
        """«excel» o «las cuentas» son preguntas claras aunque sean cortas."""
        for pregunta in ("excel", "la letra", "las cuentas", "que tasa", "imprimir"):
            with self.subTest(pregunta=pregunta):
                respuesta = asistente.responder(pregunta, self.dominio)
                self.assertNotIn("No estoy seguro", respuesta)

    def test_sigue_rechazando_lo_que_no_sabe(self):
        for pregunta in ("cual es la capital de francia", "quien gano el mundial",
                         "receta de ceviche", "el clima de hoy", "futbol", "una cancion"):
            with self.subTest(pregunta=pregunta):
                self.assertIn("No estoy seguro", asistente.responder(pregunta, self.dominio))

    def test_las_palabras_vacias_no_deciden(self):
        """«de», «que» o «la» no pueden hacer que una ficha gane."""
        for pregunta in ("de la", "que es", "para el"):
            with self.subTest(pregunta=pregunta):
                self.assertIn("No estoy seguro", asistente.responder(pregunta, self.dominio))


class ConclusionesDelCasoTest(TestCase):
    """«Dime las conclusiones» no es solo repetir cifras: hay que interpretarlas."""

    @classmethod
    def setUpTestData(cls):
        cls.caso = crear_caso_demo(COMERCIALIZADORA_SUR)
        cls.dominio = cls.caso.a_dominio()

    def test_la_reconoce_de_varias_formas(self):
        for pregunta in ("dime las conclusiones de comercializadora del sur s.a.c",
                         "conclusiones", "analiza el caso", "que opinas",
                         "interpretacion de resultados", "como le fue a la empresa",
                         "dame un analisis financiero", "que concluyes"):
            with self.subTest(pregunta=pregunta):
                self.assertIn("Conclusiones", asistente.responder(pregunta, self.dominio))

    def test_trae_los_ratios_calculados(self):
        respuesta = asistente.responder("conclusiones", self.dominio)
        self.assertIn("100,746.17", respuesta)   # utilidad neta
        self.assertIn("25.2%", respuesta)        # margen neto
        self.assertIn("60.7%", respuesta)        # margen bruto
        self.assertIn("5.86", respuesta)         # razón corriente
        self.assertIn("17.1%", respuesta)        # endeudamiento
        self.assertIn("80,542.37", respuesta)    # crédito de IGV

    def test_distingue_ganancia_de_perdida(self):
        self.assertIn("ganó", asistente.responder("conclusiones", self.dominio))
        # Un gasto enorme deja el período en pérdida.
        asiento = self.caso.asientos.order_by("numero").last()
        linea = asiento.lineas.filter(debe__gt=0).first()
        linea.debe = linea.debe + Decimal("900000")
        linea.save()
        otra = asiento.lineas.filter(haber__gt=0).first()
        otra.haber = otra.haber + Decimal("900000")
        otra.save()
        respuesta = asistente.responder("conclusiones", self.caso.a_dominio())
        self.assertIn("perdió", respuesta)
        self.assertIn("no hay impuesto", respuesta)

    def test_sin_caso_pide_abrir_uno(self):
        self.assertIn("ningún caso abierto", asistente.responder("conclusiones", None))


class CalculadoraTest(TestCase):
    """«1+1?» es una pregunta legítima y antes no se entendía."""

    def test_resuelve_operaciones(self):
        esperados = {
            "1+1?": "2", "cuanto es 2+2": "4", "5*4": "20", "(100+20)/2": "60",
            "10-3": "7", "2+2*3": "8", "calcula 7*8": "56",
        }
        for pregunta, resultado in esperados.items():
            with self.subTest(pregunta=pregunta):
                self.assertIn(resultado, asistente.responder(pregunta, None))

    def test_acepta_la_coma_de_miles_y_la_x(self):
        self.assertIn("3", asistente.responder("1,000 + 2,500", None))
        self.assertIn("472", asistente.responder("400000 x 1.18", None))

    def test_redondea_a_dos_decimales(self):
        self.assertIn("333.33", asistente.responder("1000/3", None))

    def test_avisa_si_no_puede(self):
        self.assertIn("No pude resolver", asistente.responder("1/0", None))

    def test_no_evalua_nada_que_no_sea_aritmetica(self):
        for intento in ("__import__('os')", "1+1; print(2)", "open('x')", "2**9999999"):
            with self.subTest(intento=intento):
                self.assertIsNone(asistente.calcular(intento))

    def test_no_secuestra_las_preguntas_contables(self):
        """«el IGV de 1,000,000» tiene números pero no es una cuenta suelta."""
        for pregunta in ("cuanto es el igv de 1,000,000 incluido", "cual es mi utilidad neta",
                         "que tasa usas", "como esta mi caso"):
            with self.subTest(pregunta=pregunta):
                self.assertIsNone(asistente.expresion_aritmetica(pregunta))
