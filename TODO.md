# TODO.md

Una tarea a la vez. Al terminar: marcar casilla, correr `pytest -q` completo,
hacer commit. Si algo bloquea, anotarlo bajo la tarea y seguir con la siguiente.

## Fase 0 — Datos (1 día)

- [x] **0.1** `core/db.py` con el DDL de SPEC §2 y función `get_conn()`
- [x] **0.2** `scripts/seed.py`: 12 insumos, 10 productos, recetas, 25 clientes,
      60 días de ventas con la estacionalidad de SPEC §2
- [x] **0.3** Verificar a mano con SQL: consumo de un insumo en un mes, total de
      ventas del último mes, cuántos insumos están bajo mínimo. **Anotar esos
      tres números en `evals/valores_base.md`** — son la base del dataset

## Fase 1 — Núcleo (4 días)

### Día 1-2: herramientas

- [x] **1.1** `core/models.py` con todos los modelos Pydantic de SPEC §3
- [x] **1.2** `stock_actual` + test
- [x] **1.3** `consumo_promedio` + test (incluye el caso consumo = 0)
- [x] **1.4** `ventas_por_periodo` + test (un caso por cada `agrupar_por`)
- [x] **1.5** `margen_por_producto` + test
- [x] **1.6** `clientes_inactivos` + test
- [x] **1.7** `crear_orden_compra` + test, incluyendo que **falle** si se llama
      sin aprobación en el estado
- [x] **1.8** `sugerir_compra`: la regla de SPEC §3.7 sobre las dos anteriores + test

### Día 3: el grafo

- [x] **1.9** Nodo `entender` con salida Pydantic + checkpointer SQLite
- [x] **1.10** Nodo `ejecutar_herramientas` (caso simple: una herramienta)
- [x] **1.11** Caso multi-herramienta: "¿qué compro esta semana?"
- [x] **1.12** Nodo `redactar` — probar que no invente números que no vinieron
      de una herramienta
- [x] **1.13** Rama de escritura con `interrupt` y reanudación por `thread_id`
- [ ] **1.14** Probar el ciclo completo a mano: pregunta → propuesta → pausa →
      aprobación → registro en `ordenes_compra`

### Día 4: evaluación

- [x] **1.15** `evals/dataset.yaml` con los 15 casos (incluidos los 2 ambiguos)
- [x] **1.16** `evals/run_evals.py` que escribe `resultados.md` con las dos
      métricas separadas
- [x] **1.17** Primera corrida. Anotar el resultado tal cual, sin arreglar nada
- [x] **1.18** Arreglar los fallos de enrutamiento (no los de redacción) y
      volver a correr. Guardar antes/después. Resultado: 13/15 → 15/15
      herramienta, 12/15 → 15/15 valor, en 3 arreglos + 1 corrección de
      redacción del dataset (V3, no del agente — ver
      `evals/resultado_final_1.18.md` para las dos lecturas y el criterio
      de cuándo pedir aclaración)
- [ ] **1.19** Langfuse en Docker: trazas con costo y latencia por consulta.
      Instrumentación lista (`core/tracing.py`, `config` propagado por
      `entender`/`redactar`, `evals/run_evals.py` etiqueta cada corrida con
      un `session_id`, `evals/costo_langfuse.py` reporta costo/latencia
      agregados). Falta: levantar el contenedor (ver `LANGFUSE.md`, lo
      levanta el usuario), poner las claves en `.env`, y correr los 15
      casos de verdad para tener el costo total y el promedio real

### Cierre de fase

- [ ] **1.20** `channels/mcp_server.py` exponiendo las 5 herramientas de lectura
- [ ] **1.21** Conectarlo a Claude Desktop y usarlo un día
- [ ] **1.22** README: diagrama del grafo, tabla de evaluación antes/después,
      captura de una traza con el costo. La tabla antes/después debe
      mostrar las dos lecturas de V3 (dataset original 14/15 valor vs.
      V3 corregido 15/15 valor), no solo el resultado final — ver
      `evals/resultado_final_1.18.md`

## Fase 2 — Telegram (2 días)

- [ ] **2.1** Bot que responde consultas de lectura
- [ ] **2.2** Botones inline Aprobar / Corregir sobre el `interrupt`
- [ ] **2.3** Gráficos como PNG: ventas por mes, top productos, clientes nuevos
      vs recurrentes
- [ ] **2.4** Resumen proactivo programado cada mañana
- [ ] **2.5** Usarlo una semana sin tocar código
- [ ] **2.6** Conectar `dias` y `minimo_compras` de `clientes_inactivos`, y
      `dias` de `consumo_promedio`, a `ParametrosPregunta` (hoy siempre usan
      su default fijo porque el grafo no los extrae), para poder preguntar
      por ventanas distintas a la de por defecto. Los `_kwargs_*` nuevos
      deben seguir la regla 8 de `CLAUDE.md`: si la pregunta no menciona la
      ventana, cae al default de la herramienta, no a `None`

## Fase 3 — Navegador (2-3 días)

- [ ] **3.1** Playwright MCP conectado como herramienta del grafo
- [ ] **3.2** Flujo buscar → agregar al carrito contra sitio de pruebas
- [ ] **3.3** Parada obligatoria antes del pago + resumen a Telegram
- [ ] **3.4** Credenciales en variables de entorno; nota de riesgos en el README
- [ ] **3.5** Video de 2 minutos punta a punta

## Fase 4 — Web (3 días, opcional)

- [ ] **4.1** Endpoint que expone las herramientas de lectura
- [ ] **4.2** Pantalla de histórico con rango de fechas y filtro por categoría
- [ ] **4.3** Orden de compra editable antes de aprobar

## Bitácora de bloqueos

(el agente escribe aquí lo que no pudo resolver, con la tarea y el motivo)
