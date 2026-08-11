"""Herramienta de lectura: consumo diario promedio de un insumo."""

import difflib
import sqlite3
from datetime import date, timedelta

from core.db import get_conn
from core.models import ConsumoInsumo

CONSULTA_CONSUMO_TOTAL = """
SELECT COALESCE(SUM(v.cantidad * r.cantidad), 0)
FROM ventas v
JOIN recetas r ON r.producto_id = v.producto_id
JOIN insumos i ON i.id = r.insumo_id
WHERE i.nombre = ? AND v.fecha >= ? AND v.fecha <= ?
"""

CONSULTA_DIAS_CON_VENTAS = """
SELECT COUNT(DISTINCT fecha) FROM ventas WHERE fecha >= ? AND fecha <= ?
"""


def consumo_promedio(
    insumo: str,
    dias: int = 14,
    conn: sqlite3.Connection | None = None,
    hoy: date | None = None,
) -> ConsumoInsumo:
    """Consumo diario promedio de un insumo, derivado de ventas x recetas.

    El divisor de consumo_diario es dias_con_ventas (dias reales con al
    menos una venta en la ventana), no dias_analizados (el tamano de la
    ventana solicitada): la cafeteria no abre domingos, y dividir entre
    dias de calendario subestima el consumo.
    """
    fecha_ancla = hoy if hoy is not None else date.today()
    fecha_desde = (fecha_ancla - timedelta(days=dias - 1)).isoformat()
    fecha_hasta = fecha_ancla.isoformat()

    conexion = conn if conn is not None else get_conn()
    try:
        fila_insumo = conexion.execute(
            "SELECT stock_actual FROM insumos WHERE nombre = ?", (insumo,)
        ).fetchone()
        if fila_insumo is None:
            nombres = [
                fila[0]
                for fila in conexion.execute("SELECT nombre FROM insumos").fetchall()
            ]
            sugerencias = difflib.get_close_matches(insumo, nombres, n=3, cutoff=0.6)
            mensaje = f"el insumo '{insumo}' no existe"
            if sugerencias:
                mensaje += f". ¿Quisiste decir: {', '.join(sugerencias)}?"
            raise ValueError(mensaje)
        (stock_actual,) = fila_insumo

        (consumo_total,) = conexion.execute(
            CONSULTA_CONSUMO_TOTAL, (insumo, fecha_desde, fecha_hasta)
        ).fetchone()
        (dias_con_ventas,) = conexion.execute(
            CONSULTA_DIAS_CON_VENTAS, (fecha_desde, fecha_hasta)
        ).fetchone()
    finally:
        if conn is None:
            conexion.close()

    consumo_diario = consumo_total / dias_con_ventas if dias_con_ventas > 0 else 0.0
    dias_de_cobertura = stock_actual / consumo_diario if consumo_diario > 0 else None

    return ConsumoInsumo(
        insumo=insumo,
        dias_analizados=dias,
        dias_con_ventas=dias_con_ventas,
        consumo_diario=consumo_diario,
        dias_de_cobertura=dias_de_cobertura,
    )
