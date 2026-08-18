"""Callbacks de Langfuse para trazar el grafo (tarea 1.19).

Opcional: si LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY no estan en .env, el
grafo funciona exactamente igual, sin trazas. La observabilidad nunca debe
poder bloquear que el copiloto responda una pregunta.
"""

import os

from langfuse.langchain import CallbackHandler

from core.config import get_langfuse_host, get_langfuse_public_key, get_langfuse_secret_key


def trazas_habilitadas() -> bool:
    """True si hay credenciales de Langfuse configuradas."""
    return bool(get_langfuse_public_key() and get_langfuse_secret_key())


def callbacks_langfuse() -> list:
    """Callbacks para pasarle a grafo.invoke(..., config={"callbacks": ...}).

    Vacia si faltan las claves. El SDK de Langfuse lee LANGFUSE_PUBLIC_KEY/
    LANGFUSE_SECRET_KEY/LANGFUSE_BASE_URL/LANGFUSE_HOST directo de las
    variables de entorno (python-dotenv ya las cargo en os.environ al
    importar core.config), asi que alcanza con fijar ambos nombres de host
    al contenedor local si no vinieron seteados — el default del SDK es
    Langfuse Cloud, no este contenedor — e instanciar el CallbackHandler.
    Fijar los dos nombres (no solo el que el SDK prioriza) evita depender
    de cual de los dos termine leyendo una version futura del SDK.
    """
    if not trazas_habilitadas():
        return []
    host = get_langfuse_host()
    os.environ["LANGFUSE_BASE_URL"] = host
    os.environ["LANGFUSE_HOST"] = host
    return [CallbackHandler()]
