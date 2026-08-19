"""Constantes y helpers compartidos por los tres scripts del ciclo manual."""

from core.tracing import callbacks_langfuse

THREAD_POR_DEFECTO = "manual-cli"


def config_grafo(thread_id: str) -> dict:
    """Config de grafo.invoke()/get_state() para un thread, con los
    callbacks de Langfuse (tarea 1.19) enganchados.

    Sin esto, una corrida manual no deja traza aunque el contenedor este
    arriba y las claves esten en .env: los callbacks van en el config de
    cada invoke, no se heredan solos del checkpointer ni de nada global.
    `langfuse_session_id=thread_id` agrupa los tres pasos (pedir, verificar,
    aprobar) de un mismo ciclo bajo la misma sesion en Langfuse.
    """
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks_langfuse(),
        "metadata": {"langfuse_session_id": thread_id, "langfuse_tags": ["manual"]},
    }
