"""Bot de Telegram: canal de solo lectura sobre el grafo (tarea 2.1).

Envoltorio delgado (regla 4 de CLAUDE.md): no contiene ninguna consulta SQL
ni logica de negocio, solo traduce mensajes de Telegram hacia el grafo
(core/graph.py) y la respuesta de vuelta. El grafo decide que herramienta
llamar; este modulo no sabe que herramientas existen.

Autorizacion: un unico chat_id autorizado (TELEGRAM_CHAT_ID en .env, el
mismo dueño que despues aprueba las compras). Cualquier otro chat recibe un
aviso de "no autorizado" y nunca llega a invocar el grafo, ni siquiera para
una consulta de lectura.

thread_id = str(chat.id): un chat de Telegram es un thread del checkpointer
(data/checkpoints.db), el mismo esquema que ya usan scripts/manual/.

Latencia (~11s promedio, tarea 1.19): mientras el grafo corre, este modulo
manda la accion "escribiendo..." a Telegram cada pocos segundos para que la
conversacion no parezca colgada, y corre la llamada bloqueante
grafo.invoke() en un hilo aparte (asyncio.to_thread) para no frenar el loop
de eventos del bot ni otras conversaciones mientras dura.

Propuestas pendientes: si el thread ya tiene un interrupt sin resolver (de
una pregunta anterior que disparo proponer_accion), una pregunta nueva no
se manda al grafo. Invocar sobre un thread pausado lo tomaria como un run
nuevo desde START y dejaria la propuesta pendiente huerfana, sin forma de
retomarla despues -- misma raiz que el bug de la tarea 1.13: asumir que el
estado del thread esta "limpio" sin chequearlo primero.
"""

import asyncio
import logging

from telegram import Chat, Update
from telegram.constants import ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from core.config import get_telegram_bot_token, get_telegram_chat_id
from core.graph import construir_grafo
from core.tracing import callbacks_langfuse

logger = logging.getLogger(__name__)

INTERVALO_TYPING_SEGUNDOS = 4.0

MENSAJE_NO_AUTORIZADO = "Este bot es privado y no esta habilitado para este chat."

MENSAJE_PROPUESTA_PENDIENTE = (
    "Hay una propuesta de compra esperando aprobacion en este chat. Por "
    "ahora no se puede aprobar desde Telegram (llega en una tarea "
    "siguiente): resolvela por otro canal antes de preguntar otra cosa."
)

MENSAJE_INTERRUPCION_SIN_BOTONES = (
    "Esa pregunta arma una propuesta de compra que necesita aprobacion "
    "humana, y todavia no puedo pedirtela por aca (llega en una tarea "
    "siguiente)."
)


def _autorizado(chat_id: int) -> bool:
    """False tambien si TELEGRAM_CHAT_ID no esta configurada todavia.

    get_telegram_chat_id() es obligatoria (lanza RuntimeError si falta) por
    disenio: no hay chat autorizado por default. Pero manejar_pregunta
    necesita loguear el chat_id de cualquier mensaje que llegue -- incluido
    antes de que la dueña haya cargado el valor en .env, que es como se
    bootstrapea ese valor la primera vez -- asi que ese caso no puede
    propagarse como excepcion sin respuesta.
    """
    try:
        chat_id_autorizado = get_telegram_chat_id()
    except RuntimeError:
        return False
    return str(chat_id) == chat_id_autorizado


def _config_grafo(thread_id: str) -> dict:
    """Config de grafo.invoke()/get_state() para el thread de un chat, con
    los callbacks de Langfuse (tarea 1.19) enganchados -- mismo patron que
    scripts/manual/_comun.config_grafo.
    """
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks_langfuse(),
        "metadata": {"langfuse_session_id": thread_id, "langfuse_tags": ["telegram"]},
    }


def _mensaje_desde_resultado(resultado: dict) -> str:
    if "__interrupt__" in resultado:
        return MENSAJE_INTERRUPCION_SIN_BOTONES
    return resultado.get("respuesta") or "No obtuve una respuesta para esa pregunta."


async def _mantener_escribiendo(chat: Chat) -> None:
    """Repite la accion "escribiendo..." cada INTERVALO_TYPING_SEGUNDOS.

    Telegram apaga el indicador solo a los ~5s; sin este loop, una llamada
    de ~11s a Gemini deja el chat con pinta de colgado bastante antes de
    que llegue la respuesta.
    """
    while True:
        await chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(INTERVALO_TYPING_SEGUNDOS)


async def manejar_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not _autorizado(chat.id):
        logger.warning("mensaje de chat no autorizado: %s", chat.id)
        await update.message.reply_text(MENSAJE_NO_AUTORIZADO)
        return

    thread_id = str(chat.id)
    grafo = context.bot_data["grafo"]
    config = _config_grafo(thread_id)

    if grafo.get_state(config).next:
        await update.message.reply_text(MENSAJE_PROPUESTA_PENDIENTE)
        return

    tarea_typing = asyncio.create_task(_mantener_escribiendo(chat))
    try:
        resultado = await asyncio.to_thread(
            grafo.invoke, {"pregunta": update.message.text}, config
        )
    finally:
        tarea_typing.cancel()

    await update.message.reply_text(_mensaje_desde_resultado(resultado))


def construir_aplicacion() -> Application:
    aplicacion = Application.builder().token(get_telegram_bot_token()).build()
    aplicacion.bot_data["grafo"] = construir_grafo()
    aplicacion.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_pregunta))
    return aplicacion


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    construir_aplicacion().run_polling()


if __name__ == "__main__":
    main()
