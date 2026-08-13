"""El grafo LangGraph del copiloto. Por ahora, solo el nodo entender."""

import difflib
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path
from typing import Literal, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from core.config import get_gemini_api_key, get_gemini_model
from core.db import get_conn

CHECKPOINT_DB_PATH = Path("data/checkpoints.db")

NombreHerramienta = Literal[
    "stock_actual",
    "consumo_promedio",
    "ventas_por_periodo",
    "margen_por_producto",
    "clientes_inactivos",
    "sugerir_compra",
]

HERRAMIENTAS_DISPONIBLES = """
- stock_actual(proveedor?): stock de cada insumo y si esta por debajo del minimo.
- consumo_promedio(insumo, dias?): consumo diario promedio de un insumo.
- ventas_por_periodo(desde, hasta, agrupar_por): ventas agrupadas por dia,
  semana, mes, producto o categoria.
- margen_por_producto(mes): margen de cada producto en un mes (YYYY-MM).
- clientes_inactivos(dias?, minimo_compras?): clientes frecuentes que dejaron
  de comprar.
- sugerir_compra(): que insumos comprar esta semana, con cantidad y urgencia.
"""


class ParametrosPregunta(BaseModel):
    insumo: str | None = None
    proveedor: str | None = None
    mes: str | None = None
    desde: date | None = None
    hasta: date | None = None
    agrupar_por: str | None = None


class Intencion(BaseModel):
    herramientas: list[NombreHerramienta]
    ambigua: bool
    motivo: str | None = None


class SalidaEntender(BaseModel):
    intencion: Intencion
    parametros: ParametrosPregunta


class EstadoGrafo(TypedDict):
    pregunta: str
    intencion: Intencion | None
    parametros: ParametrosPregunta | None
    resultados_herramientas: dict
    accion_propuesta: dict | None
    aprobacion: dict | None
    respuesta: str | None


def _sin_tildes(texto: str) -> str:
    """Quita diacriticos y pasa a minusculas, para comparar sin tildes."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def normalizar_insumo(insumo: str, conn: sqlite3.Connection) -> str:
    """Hace calzar el insumo mencionado en la pregunta contra insumos.nombre.

    La pregunta puede traer tildes ("platano") que la base no tiene. Primero
    intenta un match exacto ignorando tildes/mayusculas; si no hay, cae a
    difflib para tolerar errores de tipeo. Si tampoco encuentra nada
    razonable, devuelve el texto tal cual: no inventa un nombre que no existe.
    """
    nombres = [
        fila[0] for fila in conn.execute("SELECT nombre FROM insumos").fetchall()
    ]
    objetivo = _sin_tildes(insumo)
    for nombre in nombres:
        if _sin_tildes(nombre) == objetivo:
            return nombre

    coincidencias = difflib.get_close_matches(insumo, nombres, n=1, cutoff=0.6)
    return coincidencias[0] if coincidencias else insumo


def _clasificar(pregunta: str, hoy: date | None = None) -> SalidaEntender:
    """Llama a Gemini para clasificar la intencion y extraer parametros.

    Separada de entender() para poder monkeypatchearla en pruebas sin llamar
    a la API real.
    """
    fecha_ancla = hoy if hoy is not None else date.today()
    cliente = ChatGoogleGenerativeAI(
        model=get_gemini_model(), google_api_key=get_gemini_api_key()
    )
    modelo_estructurado = cliente.with_structured_output(SalidaEntender)

    prompt = (
        "Sos el clasificador de intencion de un copiloto de operacion para "
        "una cafeteria. Dada la pregunta de la dueña, decidi que herramienta "
        "o combinacion de herramientas de la lista responde la pregunta, y "
        "extrae los parametros que mencione (fechas, insumo, proveedor, mes, "
        "como agrupar las ventas).\n\n"
        f"Hoy es {fecha_ancla.isoformat()}. Resolvé fechas relativas "
        "('esta semana', 'el mes pasado') a fechas o meses absolutos.\n\n"
        f"Herramientas disponibles:{HERRAMIENTAS_DISPONIBLES}\n"
        "Si la pregunta es ambigua o ninguna herramienta la responde, marca "
        "ambigua=True y explica por que en motivo, en vez de adivinar.\n\n"
        f"Pregunta: {pregunta}"
    )
    return modelo_estructurado.invoke(prompt)


def entender(estado: EstadoGrafo) -> dict:
    """Clasifica la intencion de la pregunta y extrae sus parametros."""
    salida = _clasificar(estado["pregunta"])

    parametros = salida.parametros
    if parametros.insumo:
        conexion = get_conn()
        try:
            parametros = parametros.model_copy(
                update={"insumo": normalizar_insumo(parametros.insumo, conexion)}
            )
        finally:
            conexion.close()

    return {"intencion": salida.intencion, "parametros": parametros}


def _checkpointer(db_path: Path | None = None) -> SqliteSaver:
    ruta = db_path if db_path is not None else CHECKPOINT_DB_PATH
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta, check_same_thread=False)
    checkpointer = SqliteSaver(conexion)
    checkpointer.setup()
    return checkpointer


def construir_grafo(checkpointer: SqliteSaver | None = None) -> StateGraph:
    """Arma el grafo. Por ahora un solo nodo: entender."""
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("entender", entender)
    grafo.add_edge(START, "entender")
    grafo.add_edge("entender", END)
    return grafo.compile(checkpointer=checkpointer or _checkpointer())
