"""Carga de configuracion desde variables de entorno (.env)."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL_POR_DEFECTO = "gemini-2.5-flash"


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
