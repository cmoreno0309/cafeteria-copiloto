# Valores base

Verificación manual de la tarea 0.3. Estos tres números son la base para
`evals/dataset.yaml` (fase 1.15) y deben coincidir con lo que devuelvan las
herramientas correspondientes (`stock_actual`, `ventas_por_periodo`,
`consumo_promedio`).

Rango de datos disponibles en `ventas`: 2026-06-13 a 2026-08-11 (fecha de hoy).
Junio y agosto están incompletos, así que el **último mes completo es julio
2026** (2026-07-01 a 2026-07-31) y es el rango usado en los valores 2 y 3.

| # | Valor | Resultado |
|---|-------|-----------|
| 1 | Insumos bajo mínimo | 3: espinaca, fresa, palta |
| 2 | Ingreso total, julio 2026 | $5481.00 |
| 3 | Consumo de plátano, julio 2026 | 16.58 kg |

## 1. Insumos bajo el mínimo

```sql
SELECT nombre, stock_actual, stock_minimo, unidad
FROM insumos
WHERE stock_actual < stock_minimo
ORDER BY nombre;
```

| nombre | stock_actual | stock_minimo | unidad |
|--------|--------------|--------------|--------|
| espinaca | 0.3 | 1.0 | kg |
| fresa | 0.8 | 2.0 | kg |
| palta | 1.0 | 3.0 | kg |

## 2. Ingreso total del último mes completo

```sql
SELECT ROUND(SUM(cantidad * precio_unitario), 2)
FROM ventas
WHERE fecha >= '2026-07-01' AND fecha <= '2026-07-31';
```

Resultado: **5481.00**

## 3. Consumo de plátano en kg, último mes completo

Derivado de ventas × recetas: por cada venta, la cantidad vendida se
multiplica por la cantidad de plátano que la receta del producto usa.

```sql
SELECT ROUND(SUM(v.cantidad * r.cantidad), 3)
FROM ventas v
JOIN recetas r ON r.producto_id = v.producto_id
JOIN insumos i ON i.id = r.insumo_id
WHERE i.nombre = 'platano'
  AND v.fecha >= '2026-07-01' AND v.fecha <= '2026-07-31';
```

Resultado: **16.58 kg**
