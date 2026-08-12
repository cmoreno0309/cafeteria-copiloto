"""Herramienta de lectura: ventas agrupadas por periodo, producto o categoria."""

import sqlite3
from datetime import date

from core.db import get_conn
from core.models import FilaVenta, ResumenVentas

AGRUPACIONES_VALIDAS = {"dia", "semana", "mes", "producto", "categoria"}

CONSULTA_TOTALES = """
SELECT COALESCE(SUM(cantidad * precio_unitario), 0), COALESCE(SUM(cantidad), 0)
FROM ventas
WHERE fecha >= ? AND fecha <= ?
"""

CONSULTAS_FILAS = {
    "dia": """
        SELECT fecha AS etiqueta,
               SUM(cantidad * precio_unitario) AS ingresos,
               SUM(cantidad) AS unidades
        FROM ventas
        WHERE fecha >= ? AND fecha <= ?
        GROUP BY etiqueta
        ORDER BY etiqueta
    """,
    "semana": """
        SELECT date(fecha, 'weekday 0', '-6 days') AS etiqueta,
               SUM(cantidad * precio_unitario) AS ingresos,
               SUM(cantidad) AS unidades
        FROM ventas
        WHERE fecha >= ? AND fecha <= ?
        GROUP BY etiqueta
        ORDER BY etiqueta
    """,
    "mes": """
        SELECT strftime('%Y-%m', fecha) AS etiqueta,
               SUM(cantidad * precio_unitario) AS ingresos,
               SUM(cantidad) AS unidades
        FROM ventas
        WHERE fecha >= ? AND fecha <= ?
        GROUP BY etiqueta
        ORDER BY etiqueta
    """,
    "producto": """
        SELECT p.nombre AS etiqueta,
               SUM(v.cantidad * v.precio_unitario) AS ingresos,
               SUM(v.cantidad) AS unidades
        FROM ventas v
        JOIN productos p ON p.id = v.producto_id
        WHERE v.fecha >= ? AND v.fecha <= ?
        GROUP BY p.nombre
        ORDER BY ingresos DESC
    """,
    "categoria": """
        SELECT p.categoria AS etiqueta,
               SUM(v.cantidad * v.precio_unitario) AS ingresos,
               SUM(v.cantidad) AS unidades
        FROM ventas v
        JOIN productos p ON p.id = v.producto_id
        WHERE v.fecha >= ? AND v.fecha <= ?
        GROUP BY p.categoria
        ORDER BY ingresos DESC
    """,
}


def ventas_por_periodo(
    desde: date,
    hasta: date,
    agrupar_por: str,
    conn: sqlite3.Connection | None = None,
) -> ResumenVentas:
    """Ventas del rango [desde, hasta], agrupadas segun `agrupar_por`.

    Los ingresos se calculan con precio_unitario de cada venta (el precio
    congelado al momento de vender), no con productos.precio_venta.
    """
    if agrupar_por not in AGRUPACIONES_VALIDAS:
        opciones = ", ".join(sorted(AGRUPACIONES_VALIDAS))
        raise ValueError(f"agrupar_por invalido: '{agrupar_por}'. Opciones: {opciones}")
    if desde > hasta:
        raise ValueError(f"desde ({desde}) es posterior a hasta ({hasta})")

    fecha_desde = desde.isoformat()
    fecha_hasta = hasta.isoformat()

    conexion = conn if conn is not None else get_conn()
    try:
        total_ingresos, total_unidades = conexion.execute(
            CONSULTA_TOTALES, (fecha_desde, fecha_hasta)
        ).fetchone()
        filas = conexion.execute(
            CONSULTAS_FILAS[agrupar_por], (fecha_desde, fecha_hasta)
        ).fetchall()
    finally:
        if conn is None:
            conexion.close()

    return ResumenVentas(
        total_ingresos=total_ingresos,
        total_unidades=total_unidades,
        filas=[
            FilaVenta(etiqueta=etiqueta, ingresos=ingresos, unidades=unidades)
            for etiqueta, ingresos, unidades in filas
        ],
    )
