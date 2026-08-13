"""Carga de configuracion desde variables de entorno (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_gemini_api_key() -> str:
    """Devuelve GEMINI_API_KEY o falla con un mensaje claro si falta."""
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Copia .env.example a .env y completa "
            "el valor antes de continuar."
        )
    return clave
