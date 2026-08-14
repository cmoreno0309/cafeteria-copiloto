"""El grafo LangGraph del copiloto."""

import difflib
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from core.config import get_gemini_api_key, get_gemini_model
from core.db import get_conn
from core.tools.clientes_inactivos import clientes_inactivos
from core.tools.consumo_promedio import consumo_promedio
from core.tools.margen_por_producto import margen_por_producto
from core.tools.stock_actual import stock_actual
from core.tools.sugerir_compra import sugerir_compra
from core.tools.ventas_por_periodo import ventas_por_periodo

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
  semana, mes, producto o categoria. Si la pregunta compara dos periodos
  (ej. "julio contra junio"), llena desde/hasta con el primer periodo y
  desde_comparacion/hasta_comparacion con el segundo.
- margen_por_producto(mes): margen de cada producto en un mes (YYYY-MM).
- clientes_inactivos(dias?, minimo_compras?): clientes frecuentes que dejaron
  de comprar.
- sugerir_compra(): que insumos comprar esta semana, con cantidad y urgencia.
  Ya orquesta stock y consumo internamente: para "que compro esta semana"
  no hace falta pedir stock_actual ni consumo_promedio por separado.
"""


class ParametrosPregunta(BaseModel):
    insumo: str | None = None
    proveedor: str | None = None
    mes: str | None = None
    desde: date | None = None
    hasta: date | None = None
    desde_comparacion: date | None = None
    hasta_comparacion: date | None = None
    agrupar_por: str | None = None


class Intencion(BaseModel):
    herramientas: list[NombreHerramienta]
    ambigua: bool
    motivo: str | None = None


class SalidaEntender(BaseModel):
    intencion: Intencion
    parametros: ParametrosPregunta


class ErrorHerramienta(BaseModel):
    """Marca en resultados_herramientas que una herramienta fallo.

    Solo cubre ValueError (dato invalido, ej. un insumo que no existe):
    es un error de negocio que redactar puede explicarle al usuario, no un
    bug. Otras excepciones se propagan como crash, como corresponde.
    """

    mensaje: str


class ResultadoHerramienta(BaseModel):
    """Una llamada a una herramienta: que se llamo, con que parametros
    exactos, y que devolvio.

    `resultado` es el modelo propio de la herramienta (ListaStock,
    ConsumoInsumo, etc.) si la llamada tuvo exito, o ErrorHerramienta si
    fallo. Se tipa `Any` porque no hay una jerarquia comun entre los
    modelos de salida de core/tools.
    """

    herramienta: NombreHerramienta
    parametros: dict
    resultado: Any


class EstadoGrafo(TypedDict):
    pregunta: str
    intencion: Intencion | None
    parametros: ParametrosPregunta | None
    resultados_herramientas: list[ResultadoHerramienta]
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


def _kwargs_stock_actual(p: ParametrosPregunta) -> dict:
    return {"proveedor": p.proveedor}


def _kwargs_consumo_promedio(p: ParametrosPregunta) -> dict:
    return {"insumo": p.insumo}


def _kwargs_ventas_por_periodo(p: ParametrosPregunta) -> dict:
    return {"desde": p.desde, "hasta": p.hasta, "agrupar_por": p.agrupar_por}


def _kwargs_margen_por_producto(p: ParametrosPregunta) -> dict:
    return {"mes": p.mes}


def _sin_parametros(p: ParametrosPregunta) -> dict:
    return {}


HERRAMIENTAS: dict[NombreHerramienta, tuple[Callable, Callable]] = {
    "stock_actual": (stock_actual, _kwargs_stock_actual),
    "consumo_promedio": (consumo_promedio, _kwargs_consumo_promedio),
    "ventas_por_periodo": (ventas_por_periodo, _kwargs_ventas_por_periodo),
    "margen_por_producto": (margen_por_producto, _kwargs_margen_por_producto),
    "clientes_inactivos": (clientes_inactivos, _sin_parametros),
    "sugerir_compra": (sugerir_compra, _sin_parametros),
}


def _llamar(
    nombre_herramienta: NombreHerramienta,
    funcion: Callable,
    kwargs: dict,
    conexion: sqlite3.Connection,
) -> ResultadoHerramienta:
    """Ejecuta una herramienta y empaqueta el resultado (o su error) con los
    parametros exactos que se usaron, para que quede trazable en la lista.

    Un ValueError (dato invalido, ej. insumo inexistente) no se propaga
    como crash: queda como ErrorHerramienta para que redactar lo explique.
    """
    try:
        resultado: Any = funcion(**kwargs, conn=conexion)
    except ValueError as error:
        resultado = ErrorHerramienta(mensaje=str(error))
    return ResultadoHerramienta(
        herramienta=nombre_herramienta, parametros=kwargs, resultado=resultado
    )


def ejecutar_herramientas(
    estado: EstadoGrafo, conn: sqlite3.Connection | None = None
) -> dict:
    """Llama las herramientas de lectura que pidio entender.

    Si la intencion vino ambigua, no llama nada: la respuesta se redacta
    directo a partir del motivo de ambiguedad. Cada llamada arma su propia
    entrada en la lista (herramienta, parametros usados, resultado), asi
    que una herramienta que falla no afecta a las demas: no hay una unica
    entrada compartida que se pueda pisar.

    Caso especial: si se pide ventas_por_periodo y la pregunta trae un
    segundo periodo para comparar (desde_comparacion/hasta_comparacion),
    se agrega una segunda entrada con esos parametros.
    """
    intencion = estado["intencion"]
    if intencion is None or intencion.ambigua:
        return {"resultados_herramientas": []}

    parametros = estado["parametros"] or ParametrosPregunta()
    conexion = conn if conn is not None else get_conn()
    try:
        resultados: list[ResultadoHerramienta] = []
        for nombre_herramienta in intencion.herramientas:
            funcion, construir_kwargs = HERRAMIENTAS[nombre_herramienta]
            resultados.append(
                _llamar(nombre_herramienta, funcion, construir_kwargs(parametros), conexion)
            )

            if (
                nombre_herramienta == "ventas_por_periodo"
                and parametros.desde_comparacion is not None
                and parametros.hasta_comparacion is not None
            ):
                kwargs_comparacion = {
                    "desde": parametros.desde_comparacion,
                    "hasta": parametros.hasta_comparacion,
                    "agrupar_por": parametros.agrupar_por,
                }
                resultados.append(
                    _llamar(
                        "ventas_por_periodo",
                        ventas_por_periodo,
                        kwargs_comparacion,
                        conexion,
                    )
                )
    finally:
        if conn is None:
            conexion.close()

    return {"resultados_herramientas": resultados}


def _checkpointer(db_path: Path | None = None) -> SqliteSaver:
    ruta = db_path if db_path is not None else CHECKPOINT_DB_PATH
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta, check_same_thread=False)
    checkpointer = SqliteSaver(conexion)
    checkpointer.setup()
    return checkpointer


def construir_grafo(checkpointer: SqliteSaver | None = None) -> StateGraph:
    """Arma el grafo: entender -> ejecutar_herramientas. Sin redactar todavia."""
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("entender", entender)
    grafo.add_node("ejecutar_herramientas", ejecutar_herramientas)
    grafo.add_edge(START, "entender")
    grafo.add_edge("entender", "ejecutar_herramientas")
    grafo.add_edge("ejecutar_herramientas", END)
    return grafo.compile(checkpointer=checkpointer or _checkpointer())
