"""Construccion del cliente de modelo, con backend elegible por config.

Dos backends sobre el mismo ChatGoogleGenerativeAI (langchain-google-genai):
"apikey" (GEMINI_API_KEY, el de siempre) y "vertex" (Vertex AI, auth por
ADC -- application-default login, sin API key). El grafo (core/graph.py)
no sabe cual de los dos esta activo, solo llama a construir_cliente_llm().
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from core.config import (
    get_gcp_location,
    get_gcp_project,
    get_gemini_api_key,
    get_gemini_model,
    get_model_backend,
)


def construir_cliente_llm() -> ChatGoogleGenerativeAI:
    """Arma el cliente de Gemini segun MODEL_BACKEND.

    Las funciones de core.config que leen la config requerida por cada
    backend lanzan RuntimeError con mensaje claro si falta algo -- eso es
    lo que permite que el fail-fast (llamar esta funcion una vez al armar
    el grafo, antes de la primera consulta) funcione para los dos modos.
    """
    modelo = get_gemini_model()
    if get_model_backend() == "vertex":
        return ChatGoogleGenerativeAI(
            model=modelo,
            vertexai=True,
            project=get_gcp_project(),
            location=get_gcp_location(),
        )
    return ChatGoogleGenerativeAI(model=modelo, google_api_key=get_gemini_api_key())
