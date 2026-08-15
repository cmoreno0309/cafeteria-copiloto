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
- consumo_promedio(insumo): consumo diario promedio de un insumo, sobre una
  ventana fija de 14 dias (no configurable desde la pregunta).
- ventas_por_periodo(desde, hasta, agrupar_por): ventas agrupadas por dia,
  semana, mes, producto o categoria. Si la pregunta compara dos periodos
  (ej. "julio contra junio"), llena desde/hasta con el primer periodo y
  desde_comparacion/hasta_comparacion con el segundo.
- margen_por_producto(mes): margen de cada producto en un mes (YYYY-MM).
- clientes_inactivos(): clientes frecuentes que dejaron de comprar, con
  umbrales fijos (no configurables desde la pregunta).
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
    if not p.insumo:
        raise ValueError("no se especifico que insumo consultar")
    return {"insumo": p.insumo}


def _kwargs_ventas_por_periodo(p: ParametrosPregunta) -> dict:
    """agrupar_por cae a 'mes' si la pregunta no especifica como agrupar
    (ej. "julio comparado con junio"): la extraccion de Gemini no siempre
    lo completa cuando la pregunta no lo menciona explicitamente, y sin
    default la herramienta rechaza el llamado con un ValueError evitable.

    desde/hasta, en cambio, no tienen un default razonable (adivinar un
    periodo cambiaria el sentido de la pregunta): si faltan, se levanta
    ValueError en vez de dejarlos pasar como None (la herramienta compara
    fechas sin validar tipos, asi que un None ahi no da ValueError sino un
    TypeError sin capturar).
    """
    if p.desde is None or p.hasta is None:
        raise ValueError("no se especifico el periodo de fechas a consultar")
    return {"desde": p.desde, "hasta": p.hasta, "agrupar_por": p.agrupar_por or "mes"}


def _kwargs_ventas_por_periodo_comparacion(p: ParametrosPregunta) -> dict:
    if p.desde_comparacion is None or p.hasta_comparacion is None:
        raise ValueError("no se especifico el periodo de comparacion")
    return {
        "desde": p.desde_comparacion,
        "hasta": p.hasta_comparacion,
        "agrupar_por": p.agrupar_por or "mes",
    }


def _kwargs_margen_por_producto(p: ParametrosPregunta) -> dict:
    """mes no tiene default: la consulta SQL de margen_por_producto filtra
    por strftime('%Y-%m', fecha) = mes, y con mes=None esa comparacion
    contra NULL simplemente no matchea nada — no levanta error, devuelve
    una lista vacia que parece (incorrectamente) "sin margenes ese mes".
    Por eso hace falta validar aca, no confiar en que la herramienta avise.
    """
    if not p.mes:
        raise ValueError("no se especifico el mes a consultar")
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
    construir_kwargs: Callable[[ParametrosPregunta], dict],
    parametros: ParametrosPregunta,
    conexion: sqlite3.Connection,
) -> ResultadoHerramienta:
    """Arma los kwargs y ejecuta la herramienta, empaquetando el resultado
    (o su error) junto con los parametros exactos que se usaron, para que
    quede trazable en la lista.

    Un ValueError armando los kwargs (campo obligatorio que la pregunta no
    menciono, ej. insumo o mes) o llamando la herramienta (dato invalido,
    ej. insumo inexistente) no se propaga como crash: queda como
    ErrorHerramienta para que redactar lo explique. `construir_kwargs` es
    quien decide, por herramienta, que campos tienen un default razonable
    y cuales deben fallar en vez de dejar pasar None.
    """
    kwargs: dict = {}
    try:
        kwargs = construir_kwargs(parametros)
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
                _llamar(nombre_herramienta, funcion, construir_kwargs, parametros, conexion)
            )

            if (
                nombre_herramienta == "ventas_por_periodo"
                and parametros.desde_comparacion is not None
                and parametros.hasta_comparacion is not None
            ):
                resultados.append(
                    _llamar(
                        "ventas_por_periodo",
                        ventas_por_periodo,
                        _kwargs_ventas_por_periodo_comparacion,
                        parametros,
                        conexion,
                    )
                )
    finally:
        if conn is None:
            conexion.close()

    return {"resultados_herramientas": resultados}


class SalidaRedactar(BaseModel):
    respuesta: str


def _resultados_para_prompt(resultados: list[ResultadoHerramienta]) -> str:
    """Serializa cada llamada a una linea legible para el prompt: la
    herramienta, los parametros exactos con los que se llamo, y su
    resultado (o error) en JSON — para que el LLM pueda referenciar cada
    numero a su origen exacto en vez de improvisar.
    """
    lineas = []
    for entrada in resultados:
        parametros_texto = ", ".join(
            f"{clave}={valor}" for clave, valor in entrada.parametros.items()
        )
        if isinstance(entrada.resultado, ErrorHerramienta):
            cuerpo = f"ERROR: {entrada.resultado.mensaje}"
        else:
            cuerpo = entrada.resultado.model_dump_json()
        lineas.append(f"- {entrada.herramienta}({parametros_texto}): {cuerpo}")
    return "\n".join(lineas)


def _generar_respuesta(
    pregunta: str, resultados: list[ResultadoHerramienta]
) -> SalidaRedactar:
    """Llama a Gemini para redactar la respuesta final.

    Separada de redactar() para poder monkeypatchearla en pruebas sin llamar
    a la API real.
    """
    cliente = ChatGoogleGenerativeAI(
        model=get_gemini_model(), google_api_key=get_gemini_api_key()
    )
    modelo_estructurado = cliente.with_structured_output(SalidaRedactar)

    prompt = (
        "Sos el redactor de respuestas de un copiloto de operacion para una "
        "cafeteria. Te paso la pregunta original de la dueña y los "
        "resultados de las herramientas que se llamaron para responderla.\n\n"
        "Reglas estrictas:\n"
        "- Usa EXCLUSIVAMENTE los numeros que aparecen, literales, en los "
        "resultados. No calcules, no estimes, no completes ni redondees "
        "ningun numero que no este ahi tal cual. Esto incluye no deducir un "
        "numero a partir de otros dos que si estan (ej. un porcentaje o una "
        "diferencia entre dos cifras): si ese numero puntual no esta, decis "
        "que no tenes ese dato, nunca lo calculas a partir de otro.\n"
        "- Responde solo lo que la pregunta pide. Si un resultado trae mas "
        "datos de los que se preguntaron (ej. el stock de los 12 insumos "
        "cuando la pregunta era por los que estan bajo el minimo), elegi de "
        "ahi unicamente los que corresponden a la pregunta — no listes el "
        "resto.\n"
        "- Si un resultado es un error, explicalo en una frase clara y en "
        "lenguaje simple, sin jerga tecnica ni el mensaje crudo de la "
        "herramienta.\n"
        "- Si no hay resultados para responder (la pregunta era ambigua y "
        "no se llamo ninguna herramienta, o lo que piden no esta entre los "
        "resultados), no inventes una respuesta ni te disculpes en "
        "generico: pedi la aclaracion concreta que hace falta.\n"
        "- Respuesta breve por defecto: se lee en el celular. Si la "
        "respuesta es una lista de items (ej. varios insumos a comprar), "
        "una linea por item, sin parrafos de relleno.\n"
        "- Si un resultado trae un campo de urgencia o prioridad (ej. "
        "urgencia='urgente' vs 'esta_semana'), conserva esa distincion en "
        "la respuesta: los items urgentes van separados de los que pueden "
        "esperar, no todos bajo una misma etiqueta o mezclados en una sola "
        "lista pareja.\n\n"
        f"Pregunta: {pregunta}\n\n"
        f"Resultados:\n{_resultados_para_prompt(resultados)}"
    )
    return modelo_estructurado.invoke(prompt)


def redactar(estado: EstadoGrafo) -> dict:
    """Redacta la respuesta final en lenguaje natural.

    Si la intencion vino ambigua (o no se pudo clasificar), no hay
    resultados que redactar: se responde directo con el motivo que explico
    entender, sin llamar al LLM de nuevo. Es la misma explicacion en
    lenguaje natural, y evita el costo y el riesgo de una segunda llamada
    que podria inventar una respuesta donde no la hay.
    """
    intencion = estado["intencion"]
    if intencion is None or intencion.ambigua:
        motivo = intencion.motivo if intencion else None
        return {
            "respuesta": motivo or "No entendí la pregunta, ¿podrías reformularla?"
        }

    salida = _generar_respuesta(estado["pregunta"], estado["resultados_herramientas"])
    return {"respuesta": salida.respuesta}


def _checkpointer(db_path: Path | None = None) -> SqliteSaver:
    ruta = db_path if db_path is not None else CHECKPOINT_DB_PATH
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta, check_same_thread=False)
    checkpointer = SqliteSaver(conexion)
    checkpointer.setup()
    return checkpointer


def construir_grafo(checkpointer: SqliteSaver | None = None) -> StateGraph:
    """Arma el grafo: entender -> ejecutar_herramientas -> redactar."""
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("entender", entender)
    grafo.add_node("ejecutar_herramientas", ejecutar_herramientas)
    grafo.add_node("redactar", redactar)
    grafo.add_edge(START, "entender")
    grafo.add_edge("entender", "ejecutar_herramientas")
    grafo.add_edge("ejecutar_herramientas", "redactar")
    grafo.add_edge("redactar", END)
    return grafo.compile(checkpointer=checkpointer or _checkpointer())
