"""Herramienta de lectura: margen por producto de un mes."""

import sqlite3
from datetime import datetime

from core.db import get_conn
from core.models import ListaMargenes, MargenProducto

CONSULTA_MARGENES = """
SELECT
    p.nombre,
    p.precio_venta,
    COALESCE(c.costo, 0) AS costo,
    SUM(v.cantidad) AS unidades_vendidas,
    SUM(v.cantidad * (v.precio_unitario - COALESCE(c.costo, 0))) AS margen_total
FROM ventas v
JOIN productos p ON p.id = v.producto_id
LEFT JOIN (
    SELECT r.producto_id AS producto_id,
           SUM(r.cantidad * i.costo_unitario) AS costo
    FROM recetas r
    JOIN insumos i ON i.id = r.insumo_id
    GROUP BY r.producto_id
) c ON c.producto_id = p.id
WHERE strftime('%Y-%m', v.fecha) = ?
GROUP BY p.id, p.nombre, p.precio_venta, costo
ORDER BY margen_total DESC
"""


def margen_por_producto(
    mes: str,
    conn: sqlite3.Connection | None = None,
) -> ListaMargenes:
    """Margen de cada producto vendido en `mes` (formato "YYYY-MM").

    Solo incluye productos con al menos una venta en el mes: si el mes no
    tuvo ventas, devuelve la lista vacia en vez de listar todo el catalogo
    en cero.

    El costo sale de la receta (suma de cantidad x insumos.costo_unitario).
    Un producto sin receta se reporta igual, con costo 0, en vez de
    omitirse.

    Ojo: `margen_unitario` y `margen_total` no son consistentes entre si
    y no deben multiplicarse uno por el otro.
    - `margen_unitario` / `margen_pct` son el margen TEORICO segun el
      precio de catalogo (`productos.precio_venta`) menos el costo.
    - `margen_total` es el margen REALMENTE obtenido: usa el
      `precio_unitario` de cada venta (el precio congelado al momento de
      vender, que puede diferir del catalogo si hubo un cambio de precio
      en el medio), sumado sobre todas las ventas del mes.
    Por eso `margen_unitario * unidades_vendidas` puede no coincidir con
    `margen_total`.
    """
    try:
        datetime.strptime(mes, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"formato de mes invalido: '{mes}'. Se espera 'YYYY-MM'") from exc

    conexion = conn if conn is not None else get_conn()
    try:
        filas = conexion.execute(CONSULTA_MARGENES, (mes,)).fetchall()
    finally:
        if conn is None:
            conexion.close()

    items = []
    for nombre, precio_venta, costo, unidades_vendidas, margen_total in filas:
        margen_unitario = precio_venta - costo
        margen_pct = margen_unitario / precio_venta * 100
        items.append(
            MargenProducto(
                producto=nombre,
                precio=precio_venta,
                costo=costo,
                margen_unitario=margen_unitario,
                margen_pct=margen_pct,
                unidades_vendidas=unidades_vendidas,
                margen_total=margen_total,
            )
        )
    return ListaMargenes(items=items)
