"""Pruebas de core/llm.py: construir_cliente_llm segun MODEL_BACKEND.

No llaman a la API real -- ChatGoogleGenerativeAI no hace red al
construirse, solo arma el objeto con la configuracion recibida.
"""

import pytest

from core.llm import construir_cliente_llm


def test_backend_apikey_no_setea_project_ni_location(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "apikey")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente = construir_cliente_llm()

    assert cliente.project is None
    assert cliente.location is None


def test_backend_vertex_setea_project_y_location(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "cafeteria-copiloto")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    cliente = construir_cliente_llm()

    assert cliente.project == "cafeteria-copiloto"
    assert cliente.location == "us-central1"


def test_backend_vertex_sin_project_falla_claro(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        construir_cliente_llm()


def test_backend_vertex_sin_location_falla_claro(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "cafeteria-copiloto")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_LOCATION"):
        construir_cliente_llm()


def test_backend_invalido_falla_claro(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "no-existe")

    with pytest.raises(RuntimeError, match="MODEL_BACKEND"):
        construir_cliente_llm()


def test_backend_apikey_sin_gemini_api_key_falla_claro(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "apikey")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        construir_cliente_llm()
