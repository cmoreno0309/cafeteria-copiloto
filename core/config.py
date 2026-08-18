"""Carga de configuracion desde variables de entorno (.env)."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL_POR_DEFECTO = "gemini-2.5-flash"
LANGFUSE_HOST_POR_DEFECTO = "http://localhost:3000"


def get_gemini_api_key() -> str:
    """Devuelve GEMINI_API_KEY o falla con un mensaje claro si falta."""
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Copia .env.example a .env y completa "
            "el valor antes de continuar."
        )
    return clave


def get_gemini_model() -> str:
    """Devuelve GEMINI_MODEL o un valor por defecto si falta, con log."""
    modelo = os.getenv("GEMINI_MODEL")
    if not modelo:
        logger.info(
            "GEMINI_MODEL no esta definida, usando el valor por defecto: %s",
            GEMINI_MODEL_POR_DEFECTO,
        )
        return GEMINI_MODEL_POR_DEFECTO
    return modelo


def get_langfuse_public_key() -> str | None:
    """Devuelve LANGFUSE_PUBLIC_KEY o None si falta.

    A diferencia de GEMINI_API_KEY, nunca lanza: las trazas son una capa de
    observabilidad opcional (tarea 1.19), no deben poder bloquear que el
    grafo responda una pregunta. Sin esta clave, core/tracing.py
    simplemente no activa los callbacks de Langfuse.
    """
    return os.getenv("LANGFUSE_PUBLIC_KEY") or None


def get_langfuse_secret_key() -> str | None:
    """Devuelve LANGFUSE_SECRET_KEY o None si falta (ver get_langfuse_public_key)."""
    return os.getenv("LANGFUSE_SECRET_KEY") or None


def get_langfuse_host() -> str:
    """Devuelve LANGFUSE_HOST o el contenedor local por defecto si falta.

    El default del SDK de Langfuse es Langfuse Cloud, no un contenedor
    local: si esta variable faltara y no se pisara el default del SDK, las
    trazas se mandarian por accidente a un servidor que no es el que este
    proyecto levanta con Docker.
    """
    host = os.getenv("LANGFUSE_HOST")
    if not host:
        logger.info(
            "LANGFUSE_HOST no esta definida, usando el contenedor local por defecto: %s",
            LANGFUSE_HOST_POR_DEFECTO,
        )
        return LANGFUSE_HOST_POR_DEFECTO
    return host
