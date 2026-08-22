"""Pruebas de channels/telegram_bot.py."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackQueryHandler

from channels import telegram_bot
from core.db import get_conn, init_db
from core.graph import _checkpointer, construir_grafo
from tests.test_graph import _salida_accion, _sembrar_insumo_con_ventas_recientes


@pytest.fixture(autouse=True)
def _sin_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)


PROPUESTA = {
    "proveedor": "Mercado de Frutas",
    "items": [
        {
            "insumo": "banana",
            "cantidad": 5.0,
            "unidad": "kg",
            "costo_unitario_estimado": 1.2,
            "urgencia": "urgente",
        }
    ],
    "total_estimado": 6.0,
}


def _update_y_context(chat_id: int, texto: str, grafo) -> tuple:
    update = MagicMock()
    update.effective_chat = MagicMock(id=chat_id)
    update.effective_chat.send_action = AsyncMock()
    update.message = MagicMock()
    update.message.text = texto
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"grafo": grafo}
    return update, context


def _update_callback(chat_id: int, data: str, grafo, texto_original: str = "Propuesta...") -> tuple:
    update = MagicMock()
    update.effective_chat = MagicMock(id=chat_id)
    update.effective_user = MagicMock(full_name="Dueña de prueba")
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.data = data
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock(text=texto_original)

    context = MagicMock()
    context.bot_data = {"grafo": grafo}
    return update, context


def test_autorizado_devuelve_true_si_el_chat_id_coincide(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert telegram_bot._autorizado(12345) is True


def test_autorizado_devuelve_false_si_el_chat_id_no_coincide(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert telegram_bot._autorizado(99999) is False


def test_autorizado_devuelve_false_sin_explotar_si_falta_telegram_chat_id(monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram_bot._autorizado(12345) is False


def test_config_grafo_usa_el_thread_id_y_tagea_telegram():
    config = telegram_bot._config_grafo("12345")
    assert config["configurable"]["thread_id"] == "12345"
    assert config["metadata"]["langfuse_session_id"] == "12345"
    assert config["metadata"]["langfuse_tags"] == ["telegram"]
    assert config["callbacks"] == []


def test_mensaje_desde_resultado_devuelve_la_respuesta():
    resultado = {"respuesta": "hay 3 insumos bajo el minimo"}
    assert telegram_bot._mensaje_desde_resultado(resultado) == resultado["respuesta"]


def test_mensaje_desde_resultado_usa_fallback_sin_respuesta():
    assert telegram_bot._mensaje_desde_resultado({}) != ""


def test_texto_propuesta_incluye_proveedor_items_y_total():
    texto = telegram_bot._texto_propuesta(PROPUESTA)
    assert "Mercado de Frutas" in texto
    assert "banana" in texto
    assert "urgente" in texto
    assert "6.0" in texto


def test_teclado_aprobacion_arma_los_dos_botones_con_el_thread_id():
    teclado = telegram_bot._teclado_aprobacion("12345")
    (fila,) = teclado.inline_keyboard
    aprobar, rechazar = fila
    assert aprobar.callback_data == "aprobar:12345"
    assert rechazar.callback_data == "rechazar:12345"


def test_manejar_pregunta_chat_no_autorizado_no_invoca_el_grafo(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    update, context = _update_y_context(99999, "¿cuánto stock hay?", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    grafo.invoke.assert_not_called()
    update.message.reply_text.assert_awaited_once_with(telegram_bot.MENSAJE_NO_AUTORIZADO)


def test_manejar_pregunta_sin_telegram_chat_id_configurada_no_crashea(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    grafo = MagicMock()
    update, context = _update_y_context(12345, "¿cuánto stock hay?", grafo)

    with caplog.at_level("WARNING"):
        asyncio.run(telegram_bot.manejar_pregunta(update, context))

    grafo.invoke.assert_not_called()
    update.message.reply_text.assert_awaited_once_with(telegram_bot.MENSAJE_NO_AUTORIZADO)
    assert "12345" in caplog.text


def test_manejar_pregunta_con_propuesta_pendiente_no_invoca_el_grafo(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=("proponer_accion",))
    update, context = _update_y_context(12345, "otra pregunta", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    grafo.invoke.assert_not_called()
    update.message.reply_text.assert_awaited_once_with(
        telegram_bot.MENSAJE_PROPUESTA_PENDIENTE
    )


def test_manejar_pregunta_invoca_el_grafo_con_el_thread_del_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=())
    grafo.invoke.return_value = {"respuesta": "quedan 2kg de espinaca"}
    update, context = _update_y_context(12345, "¿cuánta espinaca queda?", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    args, _ = grafo.invoke.call_args
    assert args[0] == {"pregunta": "¿cuánta espinaca queda?"}
    assert args[1]["configurable"]["thread_id"] == "12345"
    update.message.reply_text.assert_awaited_once_with("quedan 2kg de espinaca")


def test_manejar_pregunta_manda_la_accion_de_escribiendo_mientras_corre(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=())
    grafo.invoke.return_value = {"respuesta": "ok"}
    update, context = _update_y_context(12345, "una pregunta", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    update.effective_chat.send_action.assert_awaited_with(ChatAction.TYPING)


def test_manejar_pregunta_con_interrupt_manda_la_propuesta_con_botones(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=())
    grafo.invoke.return_value = {"__interrupt__": [MagicMock(value=PROPUESTA)]}
    update, context = _update_y_context(12345, "arma la orden de compra de frutas", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    (texto,), kwargs = update.message.reply_text.call_args
    assert "Mercado de Frutas" in texto
    teclado = kwargs["reply_markup"]
    (fila,) = teclado.inline_keyboard
    assert fila[0].callback_data == "aprobar:12345"
    assert fila[1].callback_data == "rechazar:12345"


def test_manejar_pregunta_propaga_la_excepcion_y_cancela_el_typing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=())
    grafo.invoke.side_effect = RuntimeError("Gemini caido")
    update, context = _update_y_context(12345, "una pregunta", grafo)

    with pytest.raises(RuntimeError, match="Gemini caido"):
        asyncio.run(telegram_bot.manejar_pregunta(update, context))

    update.message.reply_text.assert_not_awaited()


def test_manejar_error_loguea_y_avisa_por_telegram(caplog):
    update = MagicMock(spec=Update)
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.error = RuntimeError("boom")

    with caplog.at_level("ERROR"):
        asyncio.run(telegram_bot.manejar_error(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        telegram_bot.MENSAJE_ERROR_INESPERADO
    )
    assert "excepcion sin capturar" in caplog.text


def test_manejar_error_no_crashea_si_no_hay_update(caplog):
    context = MagicMock()
    context.error = RuntimeError("boom sin update asociado")

    with caplog.at_level("ERROR"):
        asyncio.run(telegram_bot.manejar_error(None, context))

    assert "excepcion sin capturar" in caplog.text


def test_manejar_aprobacion_chat_no_autorizado_no_toca_el_grafo(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    update, context = _update_callback(99999, "aprobar:12345", grafo)

    asyncio.run(telegram_bot.manejar_aprobacion(update, context))

    grafo.invoke.assert_not_called()
    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_not_awaited()


def test_manejar_aprobacion_sin_interrupt_pendiente_no_reintenta_el_resume(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=())
    update, context = _update_callback(12345, "aprobar:12345", grafo, "Propuesta original")

    asyncio.run(telegram_bot.manejar_aprobacion(update, context))

    grafo.invoke.assert_not_called()
    texto, kwargs = update.callback_query.edit_message_text.call_args
    assert telegram_bot.MENSAJE_PROPUESTA_YA_RESUELTA in texto[0]
    assert kwargs["reply_markup"] is None


def test_manejar_aprobacion_aprobar_resume_con_aprobada_true_y_el_nombre_de_quien_toco(
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=("proponer_accion",))
    grafo.invoke.return_value = {"respuesta": "Orden #1 creada para Mercado de Frutas: 1 items."}
    update, context = _update_callback(12345, "aprobar:12345", grafo, "Propuesta original")

    asyncio.run(telegram_bot.manejar_aprobacion(update, context))

    args, _ = grafo.invoke.call_args
    assert args[0] == Command(
        resume={"aprobada": True, "aprobada_por": "Dueña de prueba"}
    )
    assert args[1]["configurable"]["thread_id"] == "12345"
    texto, kwargs = update.callback_query.edit_message_text.call_args
    assert "Orden #1 creada" in texto[0]
    assert kwargs["reply_markup"] is None


def test_manejar_aprobacion_rechazar_resume_con_aprobada_false(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    grafo.get_state.return_value = MagicMock(next=("proponer_accion",))
    grafo.invoke.return_value = {
        "respuesta": "Orden de Mercado de Frutas no creada: quedó rechazada."
    }
    update, context = _update_callback(12345, "rechazar:12345", grafo, "Propuesta original")

    asyncio.run(telegram_bot.manejar_aprobacion(update, context))

    args, _ = grafo.invoke.call_args
    assert args[0] == Command(
        resume={"aprobada": False, "aprobada_por": "Dueña de prueba"}
    )
    texto, _ = update.callback_query.edit_message_text.call_args
    assert "rechazada" in texto[0]


def test_construir_aplicacion_registra_el_manejador_de_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token-de-prueba")
    aplicacion = telegram_bot.construir_aplicacion()

    assert telegram_bot.manejar_error in aplicacion.error_handlers


def test_construir_aplicacion_registra_el_callback_de_aprobacion(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token-de-prueba")
    aplicacion = telegram_bot.construir_aplicacion()

    tipos = {type(h) for grupo in aplicacion.handlers.values() for h in grupo}
    assert CallbackQueryHandler in tipos


def test_ciclo_completo_contra_el_grafo_real_pregunta_pausa_aprobar_inserta_orden(
    tmp_path, monkeypatch
):
    """Integracion de punta a punta contra el grafo real (no un mock): una
    pregunta que arma una propuesta, el mensaje con botones que se manda,
    el tap de "Aprobar", y la fila que efectivamente queda en
    ordenes_compra. Reemplaza la verificacion manual por Telegram real, que
    depende de un proceso vivo y de la app en el celular.
    """
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    ruta_compra = tmp_path / "compra.db"
    init_db(ruta_compra)
    conexion = get_conn(ruta_compra)
    _sembrar_insumo_con_ventas_recientes(
        conexion, "fresa", "Mercado de Frutas", "batido de fresa", [1, 3, 5]
    )
    conexion.commit()
    conexion.close()

    monkeypatch.setattr("core.graph._clasificar", lambda pregunta, hoy=None, config=None: _salida_accion())
    monkeypatch.setattr("core.graph.get_conn", lambda: get_conn(ruta_compra))

    checkpointer = _checkpointer(tmp_path / "checkpoints.db")
    grafo = construir_grafo(checkpointer=checkpointer)

    update_pregunta, context = _update_y_context(12345, "arma la orden de compra de fresas", grafo)
    asyncio.run(telegram_bot.manejar_pregunta(update_pregunta, context))

    texto_propuesta, kwargs = update_pregunta.message.reply_text.call_args
    assert "Mercado de Frutas" in texto_propuesta[0]
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "aprobar:12345"

    update_callback, _ = _update_callback(12345, "aprobar:12345", grafo, texto_propuesta[0])
    asyncio.run(telegram_bot.manejar_aprobacion(update_callback, context))

    texto_final, _ = update_callback.callback_query.edit_message_text.call_args
    assert "Orden #" in texto_final[0]
    assert "creada" in texto_final[0]

    conexion = get_conn(ruta_compra)
    (total,) = conexion.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()
    (proveedor, aprobada_por) = conexion.execute(
        "SELECT proveedor, aprobada_por FROM ordenes_compra"
    ).fetchone()
    conexion.close()

    assert total == 1
    assert proveedor == "Mercado de Frutas"
    assert aprobada_por == "Dueña de prueba"


def test_configurar_logging_crea_el_archivo_de_log(tmp_path, monkeypatch):
    ruta = tmp_path / "logs" / "telegram.log"
    monkeypatch.setattr(telegram_bot, "RUTA_LOG", ruta)

    handlers_previos = list(logging.getLogger().handlers)
    try:
        telegram_bot._configurar_logging()
        assert ruta.exists()
    finally:
        logging.getLogger().handlers = handlers_previos
