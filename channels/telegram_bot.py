"""Bot de Telegram: canal de lectura y aprobacion sobre el grafo (2.1/2.2).

Envoltorio delgado (regla 4 de CLAUDE.md): no contiene ninguna consulta SQL
ni logica de negocio, solo traduce mensajes de Telegram hacia el grafo
(core/graph.py) y la respuesta de vuelta. El grafo decide que herramienta
llamar y si una propuesta de compra es valida; este modulo no sabe nada de
eso, solo dibuja lo que el grafo ya decidio y reenvia la decision humana.

Autorizacion: un unico chat_id autorizado (TELEGRAM_CHAT_ID en .env, el
mismo dueño que aprueba las compras). Cualquier otro chat recibe un aviso
de "no autorizado" y nunca llega a invocar el grafo, ni siquiera para una
consulta de lectura ni para tocar un boton de aprobacion.

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

Botones Aprobar/Rechazar (2.2): el callback_data lleva la accion y el
thread_id ("aprobar:<thread_id>" / "rechazar:<thread_id>"). Al tocar un
boton, el mensaje original se edita in-place (texto + se sacan los botones)
en vez de mandar uno nuevo, para que un segundo tap sobre el mismo mensaje
no tenga botones que tocar. Igual, por si el tap ya viajaba antes de esa
edicion (o el callback llega para un thread que ya no esta pausado por
cualquier otro motivo), manejar_aprobacion chequea el estado del grafo
antes de reanudar: si ya no hay interrupt pendiente, no reintenta el resume
a ciegas.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from langgraph.types import Command
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.config import get_telegram_bot_token, get_telegram_chat_id
from core.graph import construir_grafo
from core.tracing import callbacks_langfuse

logger = logging.getLogger(__name__)

INTERVALO_TYPING_SEGUNDOS = 4.0

RUTA_LOG = Path("logs/telegram.log")

MENSAJE_NO_AUTORIZADO = "Este bot es privado y no esta habilitado para este chat."

MENSAJE_PROPUESTA_PENDIENTE = (
    "Hay una propuesta de compra esperando aprobacion en este chat. Por "
    "ahora no se puede aprobar desde Telegram (llega en una tarea "
    "siguiente): resolvela por otro canal antes de preguntar otra cosa."
)

MENSAJE_PROPUESTA_YA_RESUELTA = (
    "Esa propuesta ya se resolvio antes; no hay nada pendiente en este chat."
)

MENSAJE_ERROR_INESPERADO = (
    "Tuve un problema respondiendo esa pregunta. Ya quedo registrado en el "
    "log; proba de nuevo en un momento."
)

PATRON_CALLBACK_APROBACION = r"^(aprobar|rechazar):(.+)$"


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
    return resultado.get("respuesta") or "No obtuve una respuesta para esa pregunta."


def _texto_propuesta(propuesta: dict) -> str:
    lineas = [f"Propuesta de compra a {propuesta['proveedor']}:"]
    for item in propuesta["items"]:
        lineas.append(
            f"- {item['insumo']}: {item['cantidad']} {item['unidad']} "
            f"(urgencia: {item['urgencia']}, "
            f"costo unitario estimado: {item['costo_unitario_estimado']})"
        )
    lineas.append(f"Total estimado: {propuesta['total_estimado']}")
    return "\n".join(lineas)


def _teclado_aprobacion(thread_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Aprobar", callback_data=f"aprobar:{thread_id}"),
                InlineKeyboardButton("Rechazar", callback_data=f"rechazar:{thread_id}"),
            ]
        ]
    )


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

    if "__interrupt__" in resultado:
        propuesta = resultado["__interrupt__"][0].value
        await update.message.reply_text(
            _texto_propuesta(propuesta), reply_markup=_teclado_aprobacion(thread_id)
        )
        return

    await update.message.reply_text(_mensaje_desde_resultado(resultado))


async def manejar_aprobacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    if not _autorizado(chat.id):
        logger.warning("callback de chat no autorizado: %s", chat.id)
        return

    accion, thread_id = query.data.split(":", 1)
    grafo = context.bot_data["grafo"]
    config = _config_grafo(thread_id)

    if not grafo.get_state(config).next:
        await query.edit_message_text(
            f"{query.message.text}\n\n{MENSAJE_PROPUESTA_YA_RESUELTA}", reply_markup=None
        )
        return

    aprobada_por = update.effective_user.full_name if update.effective_user else None
    decision = {"aprobada": accion == "aprobar", "aprobada_por": aprobada_por}
    resultado = await asyncio.to_thread(grafo.invoke, Command(resume=decision), config)

    texto = f"{query.message.text}\n\n{_mensaje_desde_resultado(resultado)}"
    await query.edit_message_text(texto, reply_markup=None)


async def manejar_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Error handler global de la Application (regla 4: es resiliencia del
    canal, no logica de negocio).

    Sin esto, una excepcion que no sea ValueError (ej. Gemini caido, timeout
    de red -- las de negocio ya las captura ejecutar_herramientas como
    ErrorHerramienta) quedaba solo en el log del proceso, sin que quien
    escribio se enterara siquiera de que su pregunta no se proceso.
    `update` llega tipado `object` porque PTB lo pasa tal cual al error
    handler y puede no ser un Update (ej. un error de red del propio
    polling, sin update asociado).
    """
    logger.error("excepcion sin capturar procesando un update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message is not None:
        await update.effective_message.reply_text(MENSAJE_ERROR_INESPERADO)


def construir_aplicacion() -> Application:
    aplicacion = Application.builder().token(get_telegram_bot_token()).build()
    aplicacion.bot_data["grafo"] = construir_grafo()
    aplicacion.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_pregunta))
    aplicacion.add_handler(
        CallbackQueryHandler(manejar_aprobacion, pattern=PATRON_CALLBACK_APROBACION)
    )
    aplicacion.add_error_handler(manejar_error)
    return aplicacion


def _configurar_logging() -> None:
    """INFO a consola y a logs/telegram.log (rotado a 1MB x 3 archivos).

    El archivo permite revisar despues que paso en una corrida que ya
    termino -- la consola sola se pierde apenas se cierra la terminal.
    """
    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(RUTA_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
        ],
        force=True,
    )


def main() -> None:
    _configurar_logging()
    # drop_pending_updates: no arrastrar mensajes/taps acumulados mientras el
    # bot estuvo caido -- ahora puede proponer compras, y un tap viejo sobre
    # un interrupt que ya no es el ultimo no debe reanudarse a ciegas.
    construir_aplicacion().run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
