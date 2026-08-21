"""Pruebas de channels/telegram_bot.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.constants import ChatAction

from channels import telegram_bot


@pytest.fixture(autouse=True)
def _sin_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)


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


def test_autorizado_devuelve_true_si_el_chat_id_coincide(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert telegram_bot._autorizado(12345) is True


def test_autorizado_devuelve_false_si_el_chat_id_no_coincide(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert telegram_bot._autorizado(99999) is False


def test_config_grafo_usa_el_thread_id_y_tagea_telegram():
    config = telegram_bot._config_grafo("12345")
    assert config["configurable"]["thread_id"] == "12345"
    assert config["metadata"]["langfuse_session_id"] == "12345"
    assert config["metadata"]["langfuse_tags"] == ["telegram"]
    assert config["callbacks"] == []


def test_mensaje_desde_resultado_devuelve_la_respuesta():
    resultado = {"respuesta": "hay 3 insumos bajo el minimo"}
    assert telegram_bot._mensaje_desde_resultado(resultado) == resultado["respuesta"]


def test_mensaje_desde_resultado_avisa_si_quedo_interrumpido():
    resultado = {"__interrupt__": [MagicMock()]}
    assert (
        telegram_bot._mensaje_desde_resultado(resultado)
        == telegram_bot.MENSAJE_INTERRUPCION_SIN_BOTONES
    )


def test_mensaje_desde_resultado_usa_fallback_sin_respuesta():
    assert telegram_bot._mensaje_desde_resultado({}) != ""


def test_manejar_pregunta_chat_no_autorizado_no_invoca_el_grafo(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    grafo = MagicMock()
    update, context = _update_y_context(99999, "¿cuánto stock hay?", grafo)

    asyncio.run(telegram_bot.manejar_pregunta(update, context))

    grafo.invoke.assert_not_called()
    update.message.reply_text.assert_awaited_once_with(telegram_bot.MENSAJE_NO_AUTORIZADO)


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
