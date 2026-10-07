"""Pruebas del asistente: el contexto del caso, el filtro de mensajes y la vista.

No llaman a la API: la respuesta del modelo se reemplaza por una falsa.
"""

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ..datos.casos_demo import COMERCIALIZADORA_SUR, CYBERTEC, crear_caso_demo
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
