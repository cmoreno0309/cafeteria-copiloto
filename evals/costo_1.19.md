# Costo y latencia de la corrida trazada (tarea 1.19)

Corrida real de los 15 casos de `evals/dataset.yaml` contra Gemini, con
`hoy=2026-08-16`, trazas de Langfuse activas (contenedor local,
`docker-compose.langfuse.yml`) y costo/latencia calculados localmente a
partir de los tokens que devuelve cada respuesta.

## Verificación de conexión

`Langfuse(...).auth_check()` → `True` contra `http://localhost:3000` con
las claves del `.env`. Un invoke de prueba (caso S2 suelto) mandó su traza
sin error antes de correr los 15 casos completos.

**Nota sobre `evals/costo_langfuse.py`:** el deployment local levantado con
`docker-compose.langfuse.yml` corre en *"Langfuse v4 events_only mode"*,
que no expone el endpoint `GET /api/public/traces` (`404`, mensaje
explícito del servidor). Por eso el costo de este documento **no** sale de
consultar la API de Langfuse después de la corrida — sale de un callback
local (`_ColectorDeUso` en `evals/run_evals.py`) que suma
`usage_metadata.input_tokens`/`output_tokens` de cada respuesta real de
Gemini, agregado por `_costo_usd()` con el precio oficial de
gemini-2.5-flash (`ai.google.dev/gemini-api/docs/pricing`, consultado
2026-08-18: $0.30/1M tokens de entrada, $2.50/1M de salida, thinking
tokens incluidos en el precio de salida). Las trazas igual se mandan y se
pueden ver en la UI de Langfuse (http://localhost:3000) por caso;
`evals/costo_langfuse.py` queda como alternativa para un deployment que sí
tenga habilitado ese endpoint.

## Resultado

- Acierto de herramienta: **15/15**
- Acierto de valor: **15/15**
- **Costo total: $0.012725**
- **Costo promedio por consulta: $0.000848**
- **Latencia promedio por consulta: 11.33s**

| id | caso | pregunta | tokens in/out | costo | latencia |
|---|---|---|---|---|---|
| 01 | S1 | ¿Qué insumos están por debajo del mínimo? | 1585/171 | $0.000903 | 16.43s |
| 02 | S2 | ¿Cuánta proteína en polvo vainilla me queda en stock? | 1591/53 | $0.000610 | 11.11s |
| 03 | S3 | ¿Cuál es el consumo promedio diario de café en grano? | 1190/153 | $0.000740 | 12.90s |
| 04 | S4 | ¿Qué debería comprar esta semana? | 1283/187 | $0.000852 | 5.29s |
| 05 | V1 | ¿Cómo fueron las ventas de julio 2026? | 1207/186 | $0.000827 | 13.78s |
| 06 | V2 | ¿Cómo vendí en julio 2026 comparado con junio 2026? | 1320/236 | $0.000986 | 24.33s |
| 07 | V3 | ¿Qué categoría generó más ingresos en julio 2026? | 1274/191 | $0.000860 | 5.77s |
| 08 | V4 | ¿Qué producto generó más ingresos en julio 2026? | 1434/189 | $0.000903 | 12.86s |
| 09 | M1 | ¿Qué producto dejó más margen total en julio 2026? | 2018/193 | $0.001088 | 5.28s |
| 10 | M2 | ¿Qué producto tiene mejor margen porcentual en julio 2026? | 2020/189 | $0.001079 | 6.06s |
| 11 | M3 | ¿Cuál es el margen unitario del capuchino en julio 2026? | 2026/176 | $0.001048 | 17.29s |
| 12 | C1 | ¿Qué clientes frecuentes dejaron de venir? | 1395/204 | $0.000929 | 16.05s |
| 13 | C2 | ¿Cuántas compras había hecho Fernando Rojas antes de dejar de venir? | 1407/149 | $0.000795 | 11.47s |
| 14 | A1 | ¿Cómo van las ventas? | 680/147 | $0.000572 | 7.69s |
| 15 | A2 | Arma la orden de compra | 679/133 | $0.000536 | 3.59s |

Los casos de márgenes (M1-M3) son los más caros en tokens de entrada
(~2000): `_resultados_para_prompt` serializa el JSON completo de
`margen_por_producto`, que trae los 10 productos con 6 campos cada uno,
aunque la pregunta pida solo uno. Candidato a optimizar si el costo por
consulta importa a escala, pero fuera de alcance de esta tarea.

session_id de Langfuse de esta corrida: `evals-2026-08-16-b1ef22c7`.
