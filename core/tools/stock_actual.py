"""Herramienta de lectura: stock actual de los insumos."""

import sqlite3

from core.db import get_conn
from core.models import ItemStock, ListaStock

CONSULTA_BASE = """
SELECT nombre, unidad, stock_actual, stock_minimo,
       stock_actual < stock_minimo AS bajo_minimo, proveedor
FROM insumos
"""


def stock_actual(
    proveedor: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> ListaStock:
    """Stock de cada insumo con su minimo y si esta por debajo.

    Si se pasa `proveedor`, filtra solo los insumos de ese proveedor.
    """
    conexion = conn if conn is not None else get_conn()
    try:
        if proveedor is None:
            filas = conexion.execute(CONSULTA_BASE).fetchall()
        else:
            filas = conexion.execute(
                CONSULTA_BASE + " WHERE proveedor = ?", (proveedor,)
            ).fetchall()
    finally:
        if conn is None:
            conexion.close()

    items = [
        ItemStock(
            nombre=nombre,
            unidad=unidad,
            stock=stock,
            minimo=minimo,
            bajo_minimo=bool(bajo_minimo),
            proveedor=proveedor_insumo,
        )
        for nombre, unidad, stock, minimo, bajo_minimo, proveedor_insumo in filas
    ]
    return ListaStock(items=items)
