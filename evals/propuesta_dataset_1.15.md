# Propuesta de dataset de evaluación (tarea 1.15)

Borrador para revisión. No es `evals/dataset.yaml` todavía — lo escribo recién
cuando confirmes que estas son las 15 preguntas que de verdad le harías al
negocio y que los valores esperados son correctos.

Distribución pedida en SPEC §5: 4 de stock y compras, 4 de ventas, 3 de
márgenes, 2 de clientes, 2 ambiguos. Cumplida abajo.

Base de datos usada: `data/cafeteria.db` tal cual está sembrada ahora mismo
(60 días de ventas, 2026-06-13 a 2026-08-11; 12 insumos, 10 productos, 25
clientes). No la toqué ni la reseeded.

## ⚠️ Aviso importante: 5 de los 15 casos dependen de la fecha real de hoy

`consumo_promedio`, `clientes_inactivos` y `sugerir_compra` no reciben un
rango de fechas — anclan su ventana a `date.today()` real en el momento en
que se llaman (`core/graph.py` no les pasa un `hoy` fijo). Por eso los casos
**S3, S4, C1, C2 y A2** están calculados con **hoy = 2026-08-16** (la fecha
real del sistema al momento de escribir esto). Si `run_evals.py` (tarea 1.16)
se corre otro día, esos 5 casos pueden dar un valor distinto al de acá abajo
— no porque el agente se haya equivocado, sino porque la ventana de 14/21
días se corrió. Los datos de venta terminan el 2026-08-11, así que en cuanto
"hoy" real pase de ~2026-08-25 esa ventana deja de tener ventas adentro y
estos 5 casos van a fallar aunque el grafo funcione perfecto.

Dos salidas posibles, para que elijas cuando lleguemos a 1.16:
1. `run_evals.py` fija `hoy=2026-08-16` al llamar estas herramientas (rompe
   la regla "no le paso fecha a mano", pero mantiene el dataset estable).
2. Cada vez que se re-corran los evals lejos de esta fecha, se recalculan
   estos 5 valores a mano contra la base tal cual esté ese día.

No usé el dato de **16.58 kg de plátano en julio** que me diste: ninguna
herramienta responde "consumo total de un insumo en un mes calendario" —
`consumo_promedio` es una ventana móvil de 14 días desde hoy, no un rango
elegible. Ese número sirvió para verificar la 0.3, pero no hay una pregunta
de negocio real que el grafo pueda resolver con él sin inventar un tool que
no existe. Si querés, puedo agregar esa capacidad como tarea nueva, pero no
la until pending.

---

## Stock y compras (4)

### S1 — reusa el valor verificado
**Pregunta:** "¿Qué insumos están por debajo del mínimo?"
**Herramienta esperada:** `stock_actual`
**Tipo:** conteo · **Valor esperado:** `3`

```sql
SELECT nombre, stock_actual, stock_minimo, unidad
FROM insumos
WHERE stock_actual < stock_minimo
ORDER BY nombre;
-- espinaca (0.3/1.0), fresa (0.8/2.0), palta (1.0/3.0)
```

### S2 — stock de un insumo puntual
**Pregunta:** "¿Cuánta proteína en polvo vainilla me queda en stock?"
**Herramienta esperada:** `stock_actual`
**Tipo:** monto (kg) · **Valor esperado:** `2.5` · tolerancia `0.01`

```sql
SELECT stock_actual, unidad FROM insumos WHERE nombre = 'proteina en polvo vainilla';
-- 2.5 kg
```

### S3 — consumo promedio ⚠️ ancla a hoy=2026-08-16
**Pregunta:** "¿Cuál es el consumo promedio diario de café en grano?"
**Herramienta esperada:** `consumo_promedio`
**Tipo:** monto (kg/día) · **Valor esperado:** `0.1035` · tolerancia `0.001`

```sql
-- ventana de 14 dias terminando hoy: 2026-08-03 a 2026-08-16
SELECT COALESCE(SUM(v.cantidad * r.cantidad), 0) AS consumo_total,
       (SELECT COUNT(DISTINCT fecha) FROM ventas
        WHERE fecha >= '2026-08-03' AND fecha <= '2026-08-16') AS dias_con_ventas
FROM ventas v
JOIN recetas r ON r.producto_id = v.producto_id
JOIN insumos i ON i.id = r.insumo_id
WHERE i.nombre = 'cafe en grano' AND v.fecha >= '2026-08-03' AND v.fecha <= '2026-08-16';
-- consumo_total = 0.828, dias_con_ventas = 8 -> consumo_diario = 0.828/8 = 0.1035
```

### S4 — qué comprar esta semana ⚠️ ancla a hoy=2026-08-16
**Pregunta:** "¿Qué debería comprar esta semana?"
**Herramienta esperada:** `sugerir_compra`
**Tipo:** conteo (total de insumos sugeridos, sumando todos los proveedores)
**Valor esperado:** `4`

Regla de SPEC §3.7 (`cobertura = stock / consumo_diario(14d)`; `<3` urgente,
`3–7` esta_semana) aplicada a mano a los 12 insumos, misma ventana que S3:

| insumo | consumo_diario | cobertura (días) | entra |
|---|---|---|---|
| fresa | 0.3125 | 2.56 | **urgente**, cantidad = ceil(0.3125×14 − 0.8) = 4 kg |
| espinaca | 0.0600 | 5.00 | **esta_semana**, cantidad = ceil(0.06×14 − 0.3) = 1 kg |
| palta | 0.2875 | 3.48 | **esta_semana**, cantidad = ceil(0.2875×14 − 1.0) = 4 kg |
| pan integral | 5.7500 | 6.96 | **esta_semana**, cantidad = ceil(5.75×14 − 40) = 41 u |
| leche de almendras | 1.5688 | 7.65 | no entra (≥7) |
| platano, avena, granola, huevo, proteina, yogurt, cafe en grano | — | todos > 7 | no entran |

Total: 4 insumos, en 2 proveedores (Mercado de Frutas: fresa/espinaca/palta;
Panadería La Espiga: pan integral).

---

## Ventas (4)

### V1 — reusa el valor verificado
**Pregunta:** "¿Cómo fueron las ventas de julio 2026?"
**Herramienta esperada:** `ventas_por_periodo` (desde=2026-07-01, hasta=2026-07-31)
**Tipo:** monto · **Valor esperado:** `5481.00` · tolerancia `0.01`

```sql
SELECT ROUND(SUM(cantidad * precio_unitario), 2)
FROM ventas WHERE fecha >= '2026-07-01' AND fecha <= '2026-07-31';
```

### V2 — comparación de dos períodos (reusa ambos valores verificados)
**Pregunta:** "¿Cómo vendí en julio 2026 comparado con junio 2026?"
**Herramienta esperada:** `ventas_por_periodo` (llamada 2 veces: julio y junio)
**Tipo:** monto (par) · **Valor esperado:** julio `5481.00`, junio `3096.00` · tolerancia `0.01`

```sql
SELECT ROUND(SUM(cantidad*precio_unitario),2) FROM ventas WHERE fecha>='2026-07-01' AND fecha<='2026-07-31'; -- 5481.00
SELECT ROUND(SUM(cantidad*precio_unitario),2) FROM ventas WHERE fecha>='2026-06-01' AND fecha<='2026-06-30'; -- 3096.00
```

### V3 — categoría top
**Pregunta:** "¿Qué categoría de productos vendió más en julio 2026?"
**Herramienta esperada:** `ventas_por_periodo` (agrupar_por=categoria)
**Tipo:** texto + monto · **Valor esperado:** `"batido"`, `1955.00`

```sql
SELECT p.categoria, SUM(v.cantidad*v.precio_unitario) AS ingresos
FROM ventas v JOIN productos p ON p.id = v.producto_id
WHERE v.fecha >= '2026-07-01' AND v.fecha <= '2026-07-31'
GROUP BY p.categoria ORDER BY ingresos DESC;
-- batido 1955.00, cafe 1307.00, snack 1137.00, bowl 1082.00
```

### V4 — producto con más ingresos
**Pregunta:** "¿Qué producto generó más ingresos en julio 2026?"
**Herramienta esperada:** `ventas_por_periodo` (agrupar_por=producto)
**Tipo:** texto + monto · **Valor esperado:** `"Batido verde detox"`, `795.00`

```sql
SELECT p.nombre, SUM(v.cantidad*v.precio_unitario) AS ingresos
FROM ventas v JOIN productos p ON p.id = v.producto_id
WHERE v.fecha >= '2026-07-01' AND v.fecha <= '2026-07-31'
GROUP BY p.nombre ORDER BY ingresos DESC LIMIT 1;
-- Batido verde detox, 795.00 (53 unidades)
```

Nota: pedí "ingresos" explícito, no "más vendido" — con "más vendido" queda
ambiguo si es por ingresos o por unidades (por unidades el primero sería
Café americano, 59 unidades, no el mismo producto).

---

## Márgenes (3)

Costo de receta = Σ(cantidad_insumo × costo_unitario). La consulta exacta es
la de `core/tools/margen_por_producto.py` (`CONSULTA_MARGENES`), filtrando
`strftime('%Y-%m', v.fecha) = '2026-07'`. Reproduzco el resultado completo
para que puedas verificar cualquier fila a mano:

| producto | precio | costo | margen_unitario | margen_pct | unidades | margen_total |
|---|---|---|---|---|---|---|
| Batido verde detox | 15.00 | 3.61 | 11.39 | 75.93% | 53 | **603.67** |
| Tostada de palta con huevo | 15.00 | 3.05 | 11.95 | 79.67% | 47 | 561.65 |
| Bowl de yogurt con granola | 16.00 | 4.85 | 11.15 | 69.69% | 40 | 446.00 |
| Batido de proteína | 18.00 | 6.80 | 11.20 | 62.22% | 38 | 425.60 |
| Café americano | 7.00 | 0.864 | 6.136 | **87.66%** | 59 | 362.02 |
| Café con leche de almendras | 12.00 | 3.664 | 8.336 | 69.47% | 42 | 350.11 |
| Tostada de palta | 12.00 | 2.45 | 9.55 | 79.58% | 36 | 343.80 |
| Bowl de avena y fruta | 13.00 | 2.94 | 10.06 | 77.38% | 34 | 342.04 |
| Batido fresa plátano | 14.00 | 4.24 | 9.76 | 69.71% | 34 | 331.84 |
| Capuchino | 10.00 | 2.964 | **7.036** | 70.36% | 39 | 274.40 |

### M1 — mejor margen total
**Pregunta:** "¿Qué producto dejó más margen total en julio 2026?"
**Herramienta esperada:** `margen_por_producto` (mes=2026-07)
**Tipo:** texto + monto · **Valor esperado:** `"Batido verde detox"`, `603.67`

### M2 — mejor margen porcentual
**Pregunta:** "¿Qué producto tiene mejor margen porcentual en julio 2026?"
**Herramienta esperada:** `margen_por_producto` (mes=2026-07)
**Tipo:** texto + monto · **Valor esperado:** `"Café americano"`, `87.66` (%) · tolerancia `0.01`

Distinta de M1 a propósito: el mejor margen _total_ no es el mismo producto
que el mejor margen _porcentual_ (café americano gana en % por costo bajísimo
pero vende poco volumen frente a los batidos).

### M3 — margen de un producto puntual
**Pregunta:** "¿Cuál es el margen unitario del capuchino en julio 2026?"
**Herramienta esperada:** `margen_por_producto` (mes=2026-07)
**Tipo:** monto · **Valor esperado:** `7.036` · tolerancia `0.01`

```sql
-- costo = 0.018 kg cafe en grano (48.00/kg) + 0.15 litro leche de almendras (14.00/litro)
--       = 0.864 + 2.10 = 2.964
-- margen_unitario = precio_venta (10.00) - costo (2.964) = 7.036
```

---

## Clientes (2)

### C1 — reusa el valor verificado ⚠️ ancla a hoy=2026-08-16
**Pregunta:** "¿Qué clientes frecuentes dejaron de venir?"
**Herramienta esperada:** `clientes_inactivos` (dias=21, minimo_compras=3, default)
**Tipo:** conteo · **Valor esperado:** `5`

```sql
SELECT c.nombre, MAX(v.fecha) AS ultima_compra, COUNT(*) AS compras_totales
FROM ventas v JOIN clientes c ON c.id = v.cliente_id
GROUP BY c.id, c.nombre
HAVING COUNT(*) >= 3 AND MAX(v.fecha) <= '2026-07-26'  -- hoy(2026-08-16) - 21 dias
ORDER BY MAX(v.fecha) ASC;
-- Fernando Rojas, Antonella Paredes, Valentina Ramirez, Sebastian Rios, Valeria Campos
```

### C2 — dato puntual de uno de esos clientes ⚠️ ancla a hoy=2026-08-16
**Pregunta:** "¿Cuántas compras había hecho Fernando Rojas antes de dejar de venir?"
**Herramienta esperada:** `clientes_inactivos`
**Tipo:** conteo · **Valor esperado:** `16`

```sql
SELECT COUNT(*) FROM ventas v JOIN clientes c ON c.id = v.cliente_id
WHERE c.nombre = 'Fernando Rojas';
-- 16 compras historicas, ultima el 2026-07-09 (38 dias antes de hoy=2026-08-16)
```

---

## Ambiguos (2)

Acá lo correcto es que el grafo pida la aclaración concreta, sin inventar un
número ni adivinar. `herramientas_esperadas` queda vacío o parcial a
propósito: el punto de estos dos casos es que la respuesta final sea una
pregunta, no un dato.

### A1 — falta el período, entender debería marcar ambigua
**Pregunta:** "¿Cómo van las ventas?"
**Herramientas esperadas:** `[]` (o `ventas_por_periodo` con error si Gemini
no la marca ambigua — cualquiera de las dos formas es correcta siempre que
la respuesta final pida el período)
**Tipo:** ambigua · **Valor esperado:** ninguno; se evalúa que la respuesta
pida aclarar el rango de fechas, no que dé un total.

### A2 — falta el proveedor, con 2 pendientes hoy ⚠️ ancla a hoy=2026-08-16
**Pregunta:** "Arma la orden de compra"
**Herramientas esperadas:** `[sugerir_compra]`, `accion=True`
**Tipo:** ambigua · **Valor esperado:** ninguno; se evalúa que la respuesta
pida elegir entre los proveedores pendientes, sin insertar nada en
`ordenes_compra`.

Con los datos de hoy (ver tabla de S4), hay dos proveedores con algo
pendiente a la vez — Mercado de Frutas y Panadería La Espiga —, así que
`proponer_accion` no puede resolver un único proveedor sin que la pregunta
lo distinga: correcto es pedir aclaración, igual que
`test_construir_propuesta_con_varios_proveedores_sin_filtro_pide_aclaracion`
en `tests/test_graph.py`.

---

## Resumen para revisar rápido

| # | Categoría | Pregunta | Valor esperado |
|---|---|---|---|
| S1 | stock | insumos bajo mínimo | 3 |
| S2 | stock | stock de proteína en polvo | 2.5 kg |
| S3 | stock ⚠️ | consumo diario de café en grano | 0.1035 kg/día |
| S4 | stock ⚠️ | qué comprar esta semana | 4 insumos |
| V1 | ventas | ventas de julio 2026 | $5481.00 |
| V2 | ventas | julio vs. junio 2026 | $5481.00 / $3096.00 |
| V3 | ventas | categoría top julio 2026 | batido, $1955.00 |
| V4 | ventas | producto con más ingresos julio 2026 | Batido verde detox, $795.00 |
| M1 | márgenes | mejor margen total julio 2026 | Batido verde detox, $603.67 |
| M2 | márgenes | mejor margen % julio 2026 | Café americano, 87.66% |
| M3 | márgenes | margen unitario del capuchino julio 2026 | $7.036 |
| C1 | clientes ⚠️ | clientes inactivos | 5 |
| C2 | clientes ⚠️ | compras históricas de Fernando Rojas | 16 |
| A1 | ambiguo | "¿Cómo van las ventas?" | pide aclaración |
| A2 | ambiguo ⚠️ | "Arma la orden de compra" | pide aclaración |

⚠️ = calculado con hoy=2026-08-16, ver aviso al principio del documento.

## Qué necesito que confirmes

1. ¿Las 15 preguntas se parecen a lo que realmente le preguntarías al
   negocio? Puedo cambiar la redacción o el enfoque de cualquiera.
2. ¿Te parece bien no usar el dato de plátano en julio (16.58 kg), por la
   razón que expliqué arriba?
3. Para los 5 casos marcados con ⚠️: ¿prefieres que `run_evals.py` fije
   `hoy=2026-08-16`, o que se recalculen a mano cada vez que se corra el
   dataset lejos de esa fecha?
