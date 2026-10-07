"""Pruebas del asistente: el contexto del caso, el filtro de mensajes y la vista.

No llaman a la API: la respuesta del modelo se reemplaza por una falsa.
"""

import json
from datetime import timedelta
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
