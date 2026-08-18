"""Pruebas de core/config.py."""

import pytest

from core.config import (
    GEMINI_MODEL_POR_DEFECTO,
    LANGFUSE_HOST_POR_DEFECTO,
    get_gemini_api_key,
    get_gemini_model,
    get_langfuse_host,
    get_langfuse_public_key,
    get_langfuse_secret_key,
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


def test_get_langfuse_public_key_devuelve_el_valor_si_esta_definida(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")

    assert get_langfuse_public_key() == "pk-lf-prueba"


def test_get_langfuse_public_key_devuelve_none_si_falta(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)

    assert get_langfuse_public_key() is None


def test_get_langfuse_public_key_devuelve_none_si_esta_vacia(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")

    assert get_langfuse_public_key() is None


def test_get_langfuse_secret_key_devuelve_el_valor_si_esta_definida(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba")

    assert get_langfuse_secret_key() == "sk-lf-prueba"


def test_get_langfuse_secret_key_devuelve_none_si_falta(monkeypatch):
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert get_langfuse_secret_key() is None


def test_get_langfuse_host_devuelve_base_url_si_esta_definida(monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://desde-base-url:3000")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    assert get_langfuse_host() == "http://desde-base-url:3000"


def test_get_langfuse_host_cae_a_host_si_falta_base_url(monkeypatch):
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "http://desde-host:3000")

    assert get_langfuse_host() == "http://desde-host:3000"


def test_get_langfuse_host_prioriza_base_url_sobre_host(monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://desde-base-url:3000")
    monkeypatch.setenv("LANGFUSE_HOST", "http://desde-host:3000")

    assert get_langfuse_host() == "http://desde-base-url:3000"


def test_get_langfuse_host_usa_default_local_y_lo_registra_si_faltan_ambas(
    monkeypatch, caplog
):
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    with caplog.at_level("INFO"):
        host = get_langfuse_host()

    assert host == LANGFUSE_HOST_POR_DEFECTO
    assert LANGFUSE_HOST_POR_DEFECTO in caplog.text


def test_get_langfuse_host_usa_default_si_ambas_estan_vacias(monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "")
    monkeypatch.setenv("LANGFUSE_HOST", "")

    assert get_langfuse_host() == LANGFUSE_HOST_POR_DEFECTO
