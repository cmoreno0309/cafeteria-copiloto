"""Pruebas de core/config.py."""

import pytest

from core.config import (
    GEMINI_MODEL_POR_DEFECTO,
    get_gemini_api_key,
    get_gemini_model,
)


def test_get_gemini_api_key_devuelve_el_valor_si_esta_definida(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    assert get_gemini_api_key() == "clave-de-prueba"


def test_get_gemini_api_key_falla_con_mensaje_claro_si_falta(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Falta GEMINI_API_KEY"):
        get_gemini_api_key()


def test_get_gemini_api_key_falla_si_esta_vacia(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")

    with pytest.raises(RuntimeError, match="Falta GEMINI_API_KEY"):
        get_gemini_api_key()


def test_get_gemini_model_devuelve_el_valor_si_esta_definida(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")

    assert get_gemini_model() == "gemini-1.5-pro"


def test_get_gemini_model_usa_default_y_lo_registra_si_falta(monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    with caplog.at_level("INFO"):
        modelo = get_gemini_model()

    assert modelo == GEMINI_MODEL_POR_DEFECTO
    assert GEMINI_MODEL_POR_DEFECTO in caplog.text


def test_get_gemini_model_usa_default_si_esta_vacia(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "")

    assert get_gemini_model() == GEMINI_MODEL_POR_DEFECTO
