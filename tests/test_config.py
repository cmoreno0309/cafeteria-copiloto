"""Pruebas de core/config.py."""

import pytest

from core.config import get_gemini_api_key


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
