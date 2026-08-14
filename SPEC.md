# SPEC.md — Copiloto de operación de la cafetería

Versión 1. Cubre las fases 0 y 1. Las fases 2 a 4 están al final, sin detallar.

## 1. Problema

La dueña necesita responder rápido cuatro tipos de pregunta sin abrir hojas de
cálculo:

- ¿Qué insumos se acaban esta semana?
- ¿Cuál es el producto con mejor y peor margen?
- ¿Cómo van las ventas comparadas con el mes pasado?
- ¿Qué clientes frecuentes dejaron de venir?

Y una acción: armar la orden de compra a partir de lo que falta, con revisión
humana antes de registrarla.

## 2. Modelo de datos

SQLite. Cuatro tablas más una de órdenes.

```sql
CREATE TABLE insumos (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE,
  unidad        TEXT NOT NULL,          -- kg, litro, unidad
  stock_actual  REAL NOT NULL,
  stock_minimo  REAL NOT NULL,
  costo_unitario REAL NOT NULL,
  proveedor     TEXT NOT NULL
);

CREATE TABLE productos (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE,
  precio_venta  REAL NOT NULL,
  categoria     TEXT NOT NULL           -- batido, bowl, cafe, snack
);

CREATE TABLE recetas (
  producto_id   INTEGER NOT NULL REFERENCES productos(id),
  insumo_id     INTEGER NOT NULL REFERENCES insumos(id),
  cantidad      REAL NOT NULL,          -- en la unidad del insumo
  PRIMARY KEY (producto_id, insumo_id)
);

CREATE TABLE clientes (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL,
  fecha_registro DATE NOT NULL
);

CREATE TABLE ventas (
  id            INTEGER PRIMARY KEY,
  fecha         DATE NOT NULL,
  cliente_id    INTEGER REFERENCES clientes(id),  -- NULL = venta sin cliente
  producto_id   INTEGER NOT NULL REFERENCES productos(id),
  cantidad      INTEGER NOT NULL,
  precio_unitario REAL NOT NULL          -- congelado al momento de la venta
);

CREATE TABLE ordenes_compra (
  id            INTEGER PRIMARY KEY,
  fecha         DATE NOT NULL,
  proveedor     TEXT NOT NULL,
  estado        TEXT NOT NULL,           -- propuesta, aprobada, rechazada
  aprobada_por  TEXT,
  aprobada_en   TIMESTAMP,
  detalle_json  TEXT NOT NULL            -- items y cantidades
);
```

**Datos semilla:** 12 insumos, 10 productos, 25 clientes, 60 días de ventas.
Estacionalidad simple: viernes y sábado 40% más de ventas que un lunes; un
producto en declive sostenido (para que `margen_por_producto` tenga algo que
mostrar); 5 clientes que dejan de comprar hace más de 30 días.

## 3. Herramientas

Cinco de lectura, una de escritura. Todas devuelven un modelo Pydantic, nunca
texto libre. Todas van en `core/tools/`.

### 3.1 `stock_actual(proveedor: str | None = None) -> ListaStock`
Stock de cada insumo con su mínimo y si está por debajo.
Salida: `items: list[ItemStock]` con `nombre, unidad, stock, minimo, bajo_minimo, proveedor`.

### 3.2 `consumo_promedio(insumo: str, dias: int = 14) -> ConsumoInsumo`
Consumo diario promedio de un insumo, derivado de ventas × recetas en la ventana.
Salida: `insumo, dias_analizados, dias_con_ventas, consumo_diario, dias_de_cobertura`.
`dias_analizados` es el tamaño de la ventana solicitada (el parámetro `dias`).
`dias_con_ventas` es el número real de días con al menos una venta dentro de
esa ventana (la cafetería no abre domingos, así que puede ser menor que
`dias_analizados`). `consumo_diario = consumo_total / dias_con_ventas` — el
divisor es `dias_con_ventas`, no `dias_analizados`, porque dividir entre días
de calendario en vez de días abiertos subestima el consumo.
`dias_de_cobertura = stock_actual / consumo_diario` (si el consumo es 0, devuelve `None`).

### 3.3 `ventas_por_periodo(desde: date, hasta: date, agrupar_por: str) -> ResumenVentas`
`agrupar_por` acepta `"dia" | "semana" | "mes" | "producto" | "categoria"`.
Salida: `total_ingresos, total_unidades, filas: list[FilaVenta]` con `etiqueta, ingresos, unidades`.

### 3.4 `margen_por_producto(mes: str) -> ListaMargenes`
`mes` en formato `YYYY-MM`. Costo del producto = suma de (cantidad × costo_unitario)
de su receta. Margen = precio_venta − costo.
Salida: `items: list[MargenProducto]` con `producto, precio, costo, margen_unitario, margen_pct, unidades_vendidas, margen_total`.

### 3.5 `clientes_inactivos(dias: int = 21, minimo_compras: int = 3) -> ListaClientes`
Clientes con al menos `minimo_compras` históricas y ninguna en los últimos `dias`.
Salida: `items: list[ClienteInactivo]` con `nombre, ultima_compra, dias_sin_venir, compras_totales, ticket_promedio`.

### 3.6 `crear_orden_compra(proveedor: str, items: list[ItemOrden], aprobacion: Aprobacion | None = None) -> OrdenCompra` (ESCRITURA)
Inserta en `ordenes_compra` con estado `aprobada`. **Solo se invoca después del
`interrupt`.** La evidencia de esa aprobación se pasa explícitamente como
`aprobacion: Aprobacion`, con `aprobada_por: str` y `aprobada_en: datetime`.
Si `aprobacion` viene en `None`, la herramienta lanza `PermissionError` y no
inserta nada: no hay forma de que la herramienta verifique por sí sola que el
`interrupt` ocurrió, así que exige que quien la llama (el nodo
`aplicar_accion` del grafo) le entregue esos dos datos, extraídos del payload
de reanudación.

### 3.7 `sugerir_compra(conn=None, hoy=None) -> ListaSugerencias`

No es machine learning, es aritmética, y así se documenta:

```
para cada insumo:
    cobertura = stock_actual / consumo_diario(14 dias)
    si cobertura < 3 dias           -> urgente
    si 3 <= cobertura < 7 dias       -> esta semana
    si no                            -> no incluir
    cantidad_sugerida = consumo_diario * 14 - stock_actual   (redondeado hacia arriba)
agrupar el resultado por proveedor
```

Sin ventas en la ventana (`consumo_diario = 0`, `dias_de_cobertura = None`) el
insumo se excluye: no hay evidencia de una tasa de consumo con la que
calcular una cantidad, sin importar cuánto stock tenga.

Se apoya en `stock_actual` y `consumo_promedio` (ventana fija de 14 días, sin
parámetro configurable). `costo_unitario_estimado` sale de una consulta
directa a `insumos.costo_unitario`, porque ninguna de esas dos herramientas
lo expone en su salida.

Salida: `proveedores: list[SugerenciaProveedor]`, cada uno con `proveedor` y
`items: list[ItemSugerido]` (`insumo, cantidad, unidad, urgencia,
costo_unitario_estimado`). El campo se llama `cantidad` (no
`cantidad_sugerida`) a propósito: mismos nombres que `ItemOrden`, para que el
grafo arme la orden propuesta sin lógica intermedia.

## 4. El grafo

`core/graph.py`. Nodos:

1. **entender** — clasifica la intención y extrae parámetros (fechas, categoría,
   insumo). Salida Pydantic, no texto.
2. **ejecutar_herramientas** — llama una o varias herramientas de lectura. Puede
   iterar: para comparar dos periodos de ventas llama `ventas_por_periodo` dos
   veces, una por periodo. Para "qué compro esta semana" llama `sugerir_compra`
   directo (esa herramienta ya orquesta `stock_actual` y `consumo_promedio`
   internamente); el grafo no repite esa lógica.
3. **decidir** — ¿la respuesta es informativa o hay una acción propuesta?
   - informativa → va a `redactar`
   - acción → va a `proponer_accion`
4. **proponer_accion** — arma la orden de compra propuesta y ejecuta `interrupt`
   con el resumen. El grafo queda en pausa con su `thread_id`.
5. **aplicar_accion** — al reanudar: si fue aprobada, llama `crear_orden_compra`;
   si fue rechazada o corregida, registra el estado correspondiente.
6. **redactar** — respuesta en lenguaje natural usando **solo** los números que
   devolvieron las herramientas.

Estado del grafo: `pregunta, intencion, parametros, resultados_herramientas,
accion_propuesta, aprobacion, respuesta`. `resultados_herramientas` es una
lista de entradas `{herramienta, parametros, resultado}`, no un diccionario
por nombre: así una misma herramienta puede llamarse más de una vez (por
ejemplo, `ventas_por_periodo` para dos periodos a comparar) y cada llamada
queda trazable por separado, con los parámetros exactos que la produjeron.
`resultado` es el modelo propio de la herramienta o un `ErrorHerramienta` si
la llamada falló; una entrada que falla no afecta a las demás.

Persistencia: checkpointer de SQLite, para que la pausa sobreviva a un reinicio.

## 5. Evaluación

`evals/dataset.yaml`, 15 casos. Formato:

```yaml
- id: 01
  pregunta: "¿Qué insumos están por debajo del mínimo?"
  herramientas_esperadas: [stock_actual]
  valor_esperado: 3          # cantidad de insumos bajo mínimo en los datos semilla
  tipo: conteo

- id: 07
  pregunta: "¿Cuánto vendí en enero comparado con diciembre?"
  herramientas_esperadas: [ventas_por_periodo]
  valor_esperado: 4820.50
  tipo: monto
  tolerancia: 0.01
```

Distribución de los 15 casos: 4 de stock y compras, 4 de ventas, 3 de márgenes,
2 de clientes, 2 ambiguos (donde lo correcto es pedir aclaración, no adivinar).

Se miden **dos cosas por separado**:

| Métrica | Qué mide |
|---|---|
| Acierto de herramienta | ¿llamó exactamente las herramientas esperadas? |
| Acierto de valor | ¿el número de la respuesta coincide con el esperado? |

`run_evals.py` escribe `evals/resultados.md` con una fila por caso y el total.
El valor esperado de cada caso se calcula con una consulta SQL escrita a mano,
no con el agente.

**Umbral para dar la fase por cerrada: 13 de 15 en ambas métricas.**

## 6. Fuera de alcance (explícito)

- Toma de pedidos, caja, facturación
- Login, usuarios, permisos
- Predicción con machine learning
- Interfaz web (fase 4)
- Datos reales del negocio: todo sintético mientras sea proyecto de portafolio

## 7. Fases siguientes (sin detallar aún)

- **Fase 2 — Telegram:** consultas, botones Aprobar/Corregir sobre el `interrupt`,
  gráficos como PNG, resumen proactivo programado cada mañana.
- **Fase 3 — Navegador:** Playwright MCP como herramienta; llena el carrito del
  proveedor y se detiene antes del pago. Demo contra sitio de pruebas.
- **Fase 4 — Web:** una pantalla con histórico explorable y la orden editable.
