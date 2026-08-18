# Resultados de evaluación

Corrida contra una copia temporal de `data/cafeteria.db` (la base real no se toca). Fecha de referencia (`hoy`) usada para anclar consumo_promedio, clientes_inactivos y sugerir_compra: `2026-08-16`.

- Acierto de herramienta: **13/15** (umbral de cierre: 13/15)
- Acierto de valor: **13/15** (umbral de cierre: 13/15)

| id | caso | categoría | pregunta | herramienta | valor | detalle |
|---|---|---|---|---|---|---|
| 01 | S1 | stock | ¿Qué insumos están por debajo del mínimo? | OK | OK |  |
| 02 | S2 | stock | ¿Cuánta proteína en polvo vainilla me queda en stock? | OK | OK |  |
| 03 | S3 | stock | ¿Cuál es el consumo promedio diario de café en grano? | OK | OK |  |
| 04 | S4 | stock | ¿Qué debería comprar esta semana? | OK | OK |  |
| 05 | V1 | ventas | ¿Cómo fueron las ventas de julio 2026? | OK | OK |  |
| 06 | V2 | ventas | ¿Cómo vendí en julio 2026 comparado con junio 2026? | OK | OK |  |
| 07 | V3 | ventas | ¿Qué categoría de productos vendió más en julio 2026? | OK | FALLA | falta 'batido'; falta un numero cercano a 1955.0 |
| 08 | V4 | ventas | ¿Qué producto generó más ingresos en julio 2026? | OK | OK |  |
| 09 | M1 | margenes | ¿Qué producto dejó más margen total en julio 2026? | OK | OK |  |
| 10 | M2 | margenes | ¿Qué producto tiene mejor margen porcentual en julio 2026? | OK | OK |  |
| 11 | M3 | margenes | ¿Cuál es el margen unitario del capuchino en julio 2026? | OK | OK |  |
| 12 | C1 | clientes | ¿Qué clientes frecuentes dejaron de venir? | OK | OK |  |
| 13 | C2 | clientes | ¿Cuántas compras había hecho Fernando Rojas antes de dejar de venir? | FALLA | FALLA | no aparece 16 en la respuesta |
| 14 | A1 | ambiguo | ¿Cómo van las ventas? | FALLA | OK |  |
| 15 | A2 | ambiguo | Arma la orden de compra | OK | OK |  |

## Detalle de los casos que fallaron

### 07 (V3) — ¿Qué categoría de productos vendió más en julio 2026?

- herramienta: OK — esperada `['ventas_por_periodo']`, llamada `['ventas_por_periodo']`
- valor: FALLA — falta 'batido'; falta un numero cercano a 1955.0
- respuesta del agente: La categoría con mayor cantidad de unidades vendidas en julio 2026 fue cafe con 140 unidades.

### 13 (C2) — ¿Cuántas compras había hecho Fernando Rojas antes de dejar de venir?

- herramienta: FALLA — esperada `['clientes_inactivos']`, llamada `[]`
- valor: FALLA — no aparece 16 en la respuesta
- respuesta del agente: No existe una herramienta disponible que permita consultar el historial de compras de un cliente específico o determinar cuántas compras realizó antes de volverse inactivo.

### 14 (A1) — ¿Cómo van las ventas?

- herramienta: FALLA — esperada `[]`, llamada `['ventas_por_periodo']`
- valor: OK — 
- respuesta del agente: Entre el 1 y el 16 de agosto se registraron 1869.0 de ingresos totales y 145 unidades vendidas. Detalle por día: 2026-08-01: 260.0 ingresos, 20 unidades. 2026-08-03: 153.0 ingresos, 13 unidades. 2026-08-04: 165.0 ingresos, 13 unidades. 2026-08-05: 195.0 ingresos, 16 unidades. 2026-08-06: 200.0 ingresos, 16 unidades. 2026-08-07: 292.0 ingresos, 21 unidades. 2026-08-08: 273.0 ingresos, 21 unidades. 2026-08-10: 156.0 ingresos, 12 unidades. 2026-08-11: 175.0 ingresos, 13 unidades.
