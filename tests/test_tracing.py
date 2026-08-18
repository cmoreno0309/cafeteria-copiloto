"""Pruebas de core/tracing.py."""

import os

from langfuse.langchain import CallbackHandler

from core.tracing import callbacks_langfuse, trazas_habilitadas


def test_trazas_habilitadas_es_false_sin_claves(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert trazas_habilitadas() is False


def test_trazas_habilitadas_es_false_con_una_sola_clave(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert trazas_habilitadas() is False


def test_trazas_habilitadas_es_true_con_ambas_claves(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba")

    assert trazas_habilitadas() is True


def test_callbacks_langfuse_vacio_sin_claves(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert callbacks_langfuse() == []


def test_callbacks_langfuse_devuelve_un_callback_handler_con_claves(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba-callback")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba-callback")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    callbacks = callbacks_langfuse()

    assert len(callbacks) == 1
    assert isinstance(callbacks[0], CallbackHandler)


def test_callbacks_langfuse_fija_el_host_local_por_defecto(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba-host")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba-host")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    callbacks_langfuse()

    assert os.environ["LANGFUSE_HOST"] == "http://localhost:3000"


def test_callbacks_langfuse_respeta_un_host_ya_definido(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba-host-custom")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba-host-custom")
    monkeypatch.setenv("LANGFUSE_HOST", "http://otro-host:3000")

    callbacks_langfuse()

    assert os.environ["LANGFUSE_HOST"] == "http://otro-host:3000"
