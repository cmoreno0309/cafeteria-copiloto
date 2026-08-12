"""Herramienta de lectura: clientes frecuentes que dejaron de venir."""

import sqlite3
from datetime import date, timedelta

from core.db import get_conn
from core.models import ClienteInactivo, ListaClientes

CONSULTA_CLIENTES_INACTIVOS = """
SELECT
    c.nombre,
    MAX(v.fecha) AS ultima_compra,
    COUNT(*) AS compras_totales,
    AVG(v.cantidad * v.precio_unitario) AS ticket_promedio
FROM ventas v
JOIN clientes c ON c.id = v.cliente_id
GROUP BY c.id, c.nombre
HAVING COUNT(*) >= ? AND MAX(v.fecha) <= ?
ORDER BY MAX(v.fecha) ASC
"""


def clientes_inactivos(
    dias: int = 21,
    minimo_compras: int = 3,
    conn: sqlite3.Connection | None = None,
    hoy: date | None = None,
) -> ListaClientes:
    """Clientes frecuentes que no compran hace tiempo.

    Un cliente entra si tiene al menos `minimo_compras` compras historicas
    (el `JOIN` con `clientes` descarta las ventas con `cliente_id` nulo,
    que no cuentan para nadie) y su ultima compra fue hace `dias` dias o
    mas. La frontera es inclusiva: si la ultima compra fue hace
    EXACTAMENTE `dias` dias, el cliente cuenta como inactivo
    (`dias_sin_venir >= dias`).
    """
    fecha_ancla = hoy if hoy is not None else date.today()
    fecha_limite = fecha_ancla - timedelta(days=dias)

    conexion = conn if conn is not None else get_conn()
    try:
        filas = conexion.execute(
            CONSULTA_CLIENTES_INACTIVOS,
            (minimo_compras, fecha_limite.isoformat()),
        ).fetchall()
    finally:
        if conn is None:
            conexion.close()

    items = []
    for nombre, ultima_compra, compras_totales, ticket_promedio in filas:
        fecha_ultima_compra = date.fromisoformat(ultima_compra)
        dias_sin_venir = (fecha_ancla - fecha_ultima_compra).days
        items.append(
            ClienteInactivo(
                nombre=nombre,
                ultima_compra=fecha_ultima_compra,
                dias_sin_venir=dias_sin_venir,
                compras_totales=compras_totales,
                ticket_promedio=ticket_promedio,
            )
        )
    return ListaClientes(items=items)
