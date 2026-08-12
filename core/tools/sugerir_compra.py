"""Herramienta de lectura: que comprar segun stock y consumo (SPEC 3.7)."""

import math
import sqlite3
from datetime import date

from core.db import get_conn
from core.models import ItemSugerido, ListaSugerencias, SugerenciaProveedor
from core.tools.consumo_promedio import consumo_promedio
from core.tools.stock_actual import stock_actual

VENTANA_DIAS = 14


def _cantidad_a_comprar(consumo_diario: float, stock: float) -> float:
    """Cantidad a comprar para cubrir VENTANA_DIAS dias, redondeada hacia arriba.

    Con cobertura < 7 y consumo_diario > 0 (las unicas condiciones bajo las
    que se llega a usar este valor), el resultado matematicamente siempre
    es positivo: cantidad = consumo_diario * (VENTANA_DIAS - cobertura).
    Puede dar <= 0 solo por imprecision de punto flotante justo en el
    limite (cobertura calculada por division vs. esta resta, que pueden no
    coincidir en el ultimo bit); quien llama debe filtrar ese caso.
    """
    return math.ceil(consumo_diario * VENTANA_DIAS - stock)


def sugerir_compra(
    conn: sqlite3.Connection | None = None,
    hoy: date | None = None,
) -> ListaSugerencias:
    """Que insumos comprar, agrupados por proveedor, segun la regla de SPEC 3.7.

    Para cada insumo, la cobertura (dias_de_cobertura de consumo_promedio
    sobre una ventana fija de VENTANA_DIAS dias) decide si entra:
    cobertura < 3 -> "urgente", 3 <= cobertura < 7 -> "esta_semana", el
    resto no se incluye. La cantidad sugerida cubre VENTANA_DIAS dias de
    consumo, redondeada hacia arriba.

    Un insumo sin ventas en la ventana tiene consumo_diario = 0 y
    dias_de_cobertura = None: se excluye, porque no hay evidencia de una
    tasa de consumo con la que calcular una cantidad, sin importar cuanto
    stock tenga.

    `costo_unitario_estimado` sale de insumos.costo_unitario directo (ni
    stock_actual ni consumo_promedio lo exponen en su salida).
    """
    conexion = conn if conn is not None else get_conn()
    try:
        costos = dict(
            conexion.execute("SELECT nombre, costo_unitario FROM insumos").fetchall()
        )
        insumos = stock_actual(conn=conexion).items

        por_proveedor: dict[str, list[ItemSugerido]] = {}
        for insumo in insumos:
            consumo = consumo_promedio(
                insumo.nombre, dias=VENTANA_DIAS, conn=conexion, hoy=hoy
            )
            cobertura = consumo.dias_de_cobertura
            if cobertura is None:
                continue
            if cobertura < 3:
                urgencia = "urgente"
            elif cobertura < 7:
                urgencia = "esta_semana"
            else:
                continue

            cantidad = _cantidad_a_comprar(consumo.consumo_diario, insumo.stock)
            if cantidad <= 0:
                continue

            por_proveedor.setdefault(insumo.proveedor, []).append(
                ItemSugerido(
                    insumo=insumo.nombre,
                    cantidad=float(cantidad),
                    unidad=insumo.unidad,
                    urgencia=urgencia,
                    costo_unitario_estimado=costos[insumo.nombre],
                )
            )
    finally:
        if conn is None:
            conexion.close()

    proveedores = [
        SugerenciaProveedor(proveedor=proveedor, items=items)
        for proveedor, items in sorted(por_proveedor.items())
    ]
    return ListaSugerencias(proveedores=proveedores)
