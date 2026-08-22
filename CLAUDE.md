# CLAUDE.md

Reglas permanentes de este repo. Léelas antes de cada tarea.

## Qué es este proyecto

Copiloto de operación para una cafetería saludable. Un agente que responde
preguntas de negocio (inventario, ventas, clientes) y propone acciones de compra
que un humano aprueba antes de que se ejecuten.

NO es un punto de venta. NO toma pedidos. NO cobra.

## Stack

- Python 3.11+
- LangGraph para el grafo del agente
- Pydantic para todas las salidas estructuradas
- SQLite (`data/cafeteria.db`) vía SQLAlchemy Core o sqlite3, sin ORM pesado
- pytest para pruebas
- Langfuse (contenedor local) para trazas
- matplotlib para gráficos como imagen
- python-dotenv para cargar variables de entorno desde `.env`
- langchain-google-genai para llamar a Gemini con salida estructurada Pydantic
  (`ChatGoogleGenerativeAI(...).with_structured_output(Modelo)`), con backend
  elegible por config: API key directa o Vertex AI (`core/llm.py`)
- langgraph-checkpoint-sqlite para el checkpointer del grafo (`SqliteSaver`)
- mcp[cli] para el servidor MCP de solo lectura (`channels/mcp_server.py`)

No agregues dependencias sin decirlo en el resumen de la tarea.

## Entorno

`requirements.txt` fija las versiones exactas de las dependencias directas
(las que el código importa, no el volcado completo de `pip list`: las
transitivas las resuelve pip solo). Reconstruir el entorno desde cero:

```bash
py -m venv .venv
.venv\Scripts\activate          # PowerShell/cmd
py -m pip install -r requirements.txt
```

Si agregás una dependencia nueva (avisando en el resumen de la tarea, como
pide la regla de arriba), sumala a `requirements.txt` con la versión exacta
que quedó instalada (`pip show <paquete>`), no solo al entorno local.

## Configuración (variables de entorno)

Las variables se leen desde un archivo `.env` en la raíz del proyecto vía
`core/config.py` (usa `python-dotenv`, `load_dotenv()` se ejecuta al
importar el módulo). Trato distinto para cada una:

- `GEMINI_API_KEY` — **obligatoria con `MODEL_BACKEND=apikey`** (el default).
  `core.config.get_gemini_api_key()` lanza `RuntimeError` si falta o está
  vacía, con un mensaje que dice qué archivo copiar y completar. Nunca debe
  fallar con el error crudo de la librería de Gemini. No se usa con
  `MODEL_BACKEND=vertex`.
- `GEMINI_MODEL` — **opcional, aplica a los dos backends**.
  `core.config.get_gemini_model()` devuelve su valor si está definida; si
  falta o está vacía, devuelve `GEMINI_MODEL_POR_DEFECTO`
  (`"gemini-2.5-flash"`) y registra un log de nivel INFO indicando que se
  usó el default. Nunca falla.
- `MODEL_BACKEND` — **opcional**, `"apikey"` o `"vertex"`.
  `core.config.get_model_backend()` cae a `"apikey"`
  (`MODEL_BACKEND_POR_DEFECTO`) si falta, y lanza `RuntimeError` si tiene
  cualquier otro valor.
- `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` — **obligatorias solo
  con `MODEL_BACKEND=vertex`**. `core.config.get_gcp_project()` /
  `get_gcp_location()` lanzan `RuntimeError` si faltan. Con este backend la
  autenticación sale de ADC (`gcloud auth application-default login`), no
  de una API key.

Cualquier código que necesite estos valores debe llamar a estas funciones,
no leer `os.environ` directo.

`core/llm.py` (`construir_cliente_llm()`) es el único lugar que arma el
cliente `ChatGoogleGenerativeAI`, para cualquiera de los dos backends; el
grafo (`core/graph.py`) la llama una vez al construir el grafo
(`construir_grafo()`, antes de armar los nodos) para que una configuración
incompleta falle al arrancar el proceso, no en medio de la primera
consulta.

- `.env` guarda los valores reales y está en `.gitignore`. Nunca se commitea.
- `.env.example` documenta todas las variables vacías y sí se commitea.
- Para configurar: copiar `.env.example` a `.env` y completar los valores.

## Estructura de carpetas

```
core/
  config.py        carga de variables de entorno (.env)
  db.py            conexión y DDL
  models.py        modelos Pydantic de entrada/salida de herramientas
  tools/           una herramienta por archivo, SQL puro, sin LLM
  llm.py           construir_cliente_llm(): cliente Gemini, backend apikey/vertex
  graph.py         el grafo LangGraph
channels/
  mcp_server.py    expone las herramientas de lectura por MCP
  telegram_bot.py  bot con botones de aprobación
evals/
  dataset.yaml     preguntas de prueba con respuesta esperada
  run_evals.py     corre el dataset y escribe la tabla de resultados
scripts/
  seed.py          genera datos sintéticos
data/              la base de datos (en .gitignore)
tests/             pruebas unitarias de herramientas
```

## Reglas que no se negocian

1. **El modelo no calcula.** Ningún número (sumas, promedios, márgenes, stock)
   sale del LLM. Los calcula SQL dentro de una herramienta. El grafo solo decide
   qué herramienta llamar y redacta la respuesta con lo que recibió.
2. **Nada de SQL generado por el modelo.** Sin text-to-SQL. Las herramientas son
   consultas fijas y parametrizadas.
3. **Las herramientas no saben nada de canales.** `core/tools/` no importa nada
   de `channels/`. No conoce Telegram, ni MCP, ni HTTP.
4. **Los canales no tienen lógica de negocio.** `telegram_bot.py` no contiene ni
   una consulta SQL. Solo traduce mensajes hacia el grafo y respuestas de vuelta.
5. **`core/tools/` no menciona MCP.** MCP es un envoltorio que vive en
   `channels/mcp_server.py`. Las mismas funciones se llaman directo desde el
   grafo.
6. **Toda escritura pasa por aprobación humana.** Cualquier herramienta que
   modifique la base se ejecuta después de un `interrupt` del grafo, nunca antes.
7. **Dependencia en una sola dirección:** canales → grafo → herramientas → datos.
   Nunca al revés.
8. **Los defaults de parámetros se resuelven en el grafo, no se confía en la
   extracción del LLM.** Gemini no siempre completa un campo aunque el prompt
   lo describa como disponible: la extracción es no determinista, y una
   pregunta natural puede simplemente no mencionarlo. Cada `_kwargs_*` de
   `core/graph.py` (la función que arma los argumentos de una herramienta a
   partir de `ParametrosPregunta`) es responsable de decidir, campo por
   campo:
   - Si tiene un default razonable que **no cambia el sentido de la
     pregunta** (es una elección de formato, no de contenido — ej.
     `agrupar_por` cae a `"mes"`), se completa ahí mismo.
   - Si es parte de **lo que la pregunta pregunta** y no hay default posible
     sin inventar (ej. `insumo`, `mes`, `desde`/`hasta`), la función levanta
     `ValueError` con un mensaje claro en vez de dejar pasar `None` a la
     herramienta. Nunca asumas que la herramienta lo va a rechazar
     igual de bien: un `None` sin validar puede crashear con una excepción
     que `ejecutar_herramientas` no captura (solo captura `ValueError`), o
     peor, colar silenciosamente un resultado vacío que parece una
     respuesta real (ej. un filtro SQL contra `NULL` que no matchea nada).

## Cómo trabajar

- Una tarea de `TODO.md` a la vez. Al terminar, marca la casilla y haz commit.
- **Prueba primero.** Para cada herramienta: escribe el test con datos conocidos,
  luego la implementación, y corre pytest hasta que pase. No me preguntes si
  pasó: córrelo.
- Si una herramienta necesita un dato que la base no tiene, para y dilo. No
  inventes columnas.
- Mensajes de commit en español, imperativo, una línea: `agrega herramienta
  consumo_promedio con tests`.
- No refactorices código que no toca la tarea actual.

## Comandos

```bash
py -m pytest -q                      # todas las pruebas (excluye las marcadas @pytest.mark.api)
py -m pytest tests/test_stock.py -q  # una sola
py -m pytest -q -m api               # solo las pruebas que llaman a Gemini de verdad (cuestan dinero)
py -m scripts.seed                   # regenera datos sintéticos
py -m evals.run_evals                # corre el dataset de evaluación
py -m channels.mcp_server            # levanta el servidor MCP
```

Las pruebas marcadas con `@pytest.mark.api` (por ejemplo, los 5 casos de
`tests/test_graph.py` que verifican que `entender` clasifica bien preguntas
reales) llaman a la API de Gemini y por lo tanto cuestan dinero y necesitan
`GEMINI_API_KEY` real en `.env` más la base sembrada (`py -m scripts.seed`).
`pytest.ini` las excluye por defecto (`addopts = -m "not api"`); `-m api` en
la línea de comandos pisa ese default y corre solo esas.

## Qué preguntarme y qué no

**No me preguntes** (decide tú y anótalo en el resumen):
- nombres de variables, organización interna de un módulo, formato de docstrings
- qué librería estándar usar
- cómo estructurar un test

**Sí pregúntame** antes de avanzar:
- cambios al modelo de datos de `SPEC.md`
- cambios a la firma de una herramienta
- agregar una dependencia nueva
- cualquier cosa que rompa una de las ocho reglas de arriba

## Definición de "listo" para una tarea

1. La prueba existe y pasa.
2. No rompió las pruebas anteriores (`pytest -q` completo en verde).
3. La casilla de `TODO.md` está marcada.
4. Hay un commit.

## Idioma

Código, nombres de funciones y columnas en español (es un negocio en español).
Comentarios y docstrings en español. Sin emojis en el código ni en los commits.
