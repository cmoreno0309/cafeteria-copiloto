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

No agregues dependencias sin decirlo en el resumen de la tarea.

## Estructura de carpetas

```
core/
  db.py            conexión y DDL
  models.py        modelos Pydantic de entrada/salida de herramientas
  tools/           una herramienta por archivo, SQL puro, sin LLM
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
py -m pytest -q                      # todas las pruebas
py -m pytest tests/test_stock.py -q  # una sola
py -m scripts.seed                   # regenera datos sintéticos
py -m evals.run_evals                # corre el dataset de evaluación
py -m channels.mcp_server            # levanta el servidor MCP
```

## Qué preguntarme y qué no

**No me preguntes** (decide tú y anótalo en el resumen):
- nombres de variables, organización interna de un módulo, formato de docstrings
- qué librería estándar usar
- cómo estructurar un test

**Sí pregúntame** antes de avanzar:
- cambios al modelo de datos de `SPEC.md`
- cambios a la firma de una herramienta
- agregar una dependencia nueva
- cualquier cosa que rompa una de las siete reglas de arriba

## Definición de "listo" para una tarea

1. La prueba existe y pasa.
2. No rompió las pruebas anteriores (`pytest -q` completo en verde).
3. La casilla de `TODO.md` está marcada.
4. Hay un commit.

## Idioma

Código, nombres de funciones y columnas en español (es un negocio en español).
Comentarios y docstrings en español. Sin emojis en el código ni en los commits.
