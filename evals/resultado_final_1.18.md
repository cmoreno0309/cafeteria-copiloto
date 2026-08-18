# Resultado final de la tarea 1.18

Cuatro arreglos, aplicados uno a la vez, corriendo `py -m evals.run_evals`
contra Gemini después de cada uno (mismos 15 casos, `hoy=2026-08-16`, copia
temporal de `data/cafeteria.db`). Progresión completa, con el resultado de
cada paso guardado en su propio archivo:

| Corrida | Herramienta | Valor | Qué cambió |
|---|---|---|---|
| [Línea base (1.17)](baseline_1.17.md) | 13/15 | 12/15 | — |
| [Paso 1](paso1_1.18.md): grading de `conteo` cuenta items mencionados, no solo el número literal | 13/15 | 13/15 | C1 pasa (era fallo del evaluador, no del agente) |
| [Paso 2](paso2_1.18.md): refuerza en el prompt de `entender` que un período ausente se pregunta | 14/15 | 13/15 | A1 pasa |
| [Paso 3](paso3_1.18.md): documenta que `clientes_inactivos` trae `compras_totales`/`ticket_promedio` | 15/15 | 14/15 | C2 pasa |
| Paso 4a — **dataset original**, con los 3 arreglos de arriba ya aplicados | 15/15 | 14/15 | V3 sigue fallando |
| Paso 4b — **V3 corregido** (esta corrida) | **15/15** | **15/15** | V3 pasa |

El paso 4a es exactamente el resultado del paso 3 (`paso3_1.18.md`): no se
volvió a correr con la pregunta original de V3 porque el paso 3 ya la tenía
sin tocar. El paso 4b es esta corrida, después de reescribir la pregunta.

## V3: por qué el 15/15 final no es comparable 1 a 1 con el 13/15 inicial

**V3 se resolvió corrigiendo la pregunta del dataset, no el comportamiento
del agente.** La pregunta original era:

> ¿Qué categoría de productos vendió más en julio 2026?

En las 3 corridas donde se probó esta redacción (1.17, y los pasos 1 a 3 de
1.18), el agente respondió de forma consistente con la categoría que más
**unidades** vendió (café, 140 unidades) — el dataset esperaba la que más
**ingresos** generó (batido, $1955.00). No es un fallo ni un fluke: es una
ambigüedad real de la frase ("vendió más" no dice de qué), la misma que ya
se había evitado a propósito en V4 pidiendo "ingresos" explícito (ver su
nota en `evals/dataset.yaml`). Se corrigió V3 para pedir lo mismo:

> ¿Qué categoría generó más ingresos en julio 2026?

`evals/dataset.yaml` guarda la pregunta original en `pregunta_original` del
caso V3, con una nota explicando el porqué. El 15/15 final se logra con la
pregunta corregida — con la original, el techo real de este dataset (dados
los 3 arreglos del agente) es **15/15 herramienta, 14/15 valor**, no 15/15
parejo. Cualquier comparación futura contra este resultado debería aclarar
cuál de las dos lecturas está usando.

## Criterio: cuándo pedir aclaración y cuándo no

Lo más valioso que salió de esta evaluación no es el número final, es esta
regla, extraída de comparar los tres casos ambiguos del dataset:

| Caso | Pide aclaración | Por qué |
|---|---|---|
| **A1** — falta el período ("¿cómo van las ventas?") | Sí | Sin período, *cualquier* respuesta contesta una pregunta que nadie hizo. Antes del paso 2, el agente inventaba un rango ("del 1 al 16 de agosto") y daba un total real de un período que la dueña no pidió — el fallo más grave del dataset: no una cifra mal calculada, sino la respuesta a otra pregunta. |
| **A2** — dos proveedores con compras pendientes a la vez | Sí | Ejecutar la orden del proveedor equivocado es una acción real e irreversible sin la aprobación explícita del correcto. |
| **V3** — "vendió más" ambiguo entre ingresos y unidades | **No** | El período y la herramienta ya son correctos; la única duda es qué métrica priorizar entre dos que la propia herramienta devuelve juntas en el mismo resultado. Cualquier interpretación razonable sigue siendo información de negocio útil, no un dato inventado ni una acción irreversible. |

**Regla general:** pedir aclaración cuando adivinar puede (a) devolver un
dato que no corresponde a nada que se pidió, o (b) ejecutar una acción
irreversible sobre la elección equivocada. No pedirla por una variación de
fraseo cuando toda interpretación razonable sigue siendo útil — eso solo
agrega fricción a preguntas que un dueño de negocio haría en el día a día
sin pensarlas dos veces.

Consecuencia práctica: el arreglo de V3 fue en el dataset (redactar la
pregunta sin ambigüedad, como ya se hacía en V4), no en el agente. Enseñarle
al agente a frenar por cualquier "más"/"mejor"/"peor" ambiguo habría sido
más caro en fricción de uso que el problema que resolvía.

## Tabla completa de la corrida final (paso 4b, V3 corregido)

| id | caso | categoría | pregunta | herramienta | valor |
|---|---|---|---|---|---|
| 01 | S1 | stock | ¿Qué insumos están por debajo del mínimo? | OK | OK |
| 02 | S2 | stock | ¿Cuánta proteína en polvo vainilla me queda en stock? | OK | OK |
| 03 | S3 | stock | ¿Cuál es el consumo promedio diario de café en grano? | OK | OK |
| 04 | S4 | stock | ¿Qué debería comprar esta semana? | OK | OK |
| 05 | V1 | ventas | ¿Cómo fueron las ventas de julio 2026? | OK | OK |
| 06 | V2 | ventas | ¿Cómo vendí en julio 2026 comparado con junio 2026? | OK | OK |
| 07 | V3 | ventas | ¿Qué categoría generó más ingresos en julio 2026? | OK | OK |
| 08 | V4 | ventas | ¿Qué producto generó más ingresos en julio 2026? | OK | OK |
| 09 | M1 | margenes | ¿Qué producto dejó más margen total en julio 2026? | OK | OK |
| 10 | M2 | margenes | ¿Qué producto tiene mejor margen porcentual en julio 2026? | OK | OK |
| 11 | M3 | margenes | ¿Cuál es el margen unitario del capuchino en julio 2026? | OK | OK |
| 12 | C1 | clientes | ¿Qué clientes frecuentes dejaron de venir? | OK | OK |
| 13 | C2 | clientes | ¿Cuántas compras había hecho Fernando Rojas antes de dejar de venir? | OK | OK |
| 14 | A1 | ambiguo | ¿Cómo van las ventas? | OK | OK |
| 15 | A2 | ambiguo | Arma la orden de compra | OK | OK |

Sin casos fallidos en esta corrida.

## Pendiente para el README (tarea 1.22)

La tabla de evaluación antes/después del README tiene que mostrar **las
dos lecturas de V3**, no solo el 15/15 final: línea base (12/15 valor) →
paso 3 con dataset original (14/15 valor, techo real del agente sin tocar
V3) → final con V3 corregido (15/15 valor). Ver nota agregada en
`TODO.md`, tarea 1.22.
