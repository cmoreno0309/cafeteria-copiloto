"""Herramienta de escritura: registra una orden de compra aprobada."""

import json
import sqlite3
from datetime import date

from core.db import get_conn
from core.models import Aprobacion, ItemOrden, OrdenCompra

CONSULTA_INSERTAR = """
INSERT INTO ordenes_compra (fecha, proveedor, estado, aprobada_por, aprobada_en, detalle_json)
VALUES (?, ?, 'aprobada', ?, ?, ?)
"""


def crear_orden_compra(
    proveedor: str,
    items: list[ItemOrden],
    aprobacion: Aprobacion | None = None,
    conn: sqlite3.Connection | None = None,
    hoy: date | None = None,
) -> OrdenCompra:
    """Inserta una orden de compra aprobada en `ordenes_compra`.

    Solo se invoca despues del `interrupt` del grafo. `aprobacion` es la
    evidencia de esa aprobacion humana (quien y cuando) que el nodo
    `aplicar_accion` extrae del payload de reanudacion; si viene en
    `None` la llamada se rechaza con `PermissionError` en vez de
    insertar, porque esta herramienta no tiene forma de verificar por
    si sola que el `interrupt` ocurrio.
    """
    if not proveedor:
        raise ValueError("proveedor no puede estar vacio")
    if not items:
        raise ValueError("items no puede estar vacio")
    if aprobacion is None:
        raise PermissionError(
            "no se puede crear una orden de compra sin aprobacion humana previa"
        )

    fecha_orden = hoy if hoy is not None else date.today()
    detalle_json = json.dumps([item.model_dump(mode="json") for item in items])

    conexion = conn if conn is not None else get_conn()
    try:
        cursor = conexion.execute(
            CONSULTA_INSERTAR,
            (
                fecha_orden.isoformat(),
                proveedor,
                aprobacion.aprobada_por,
                aprobacion.aprobada_en.isoformat(),
                detalle_json,
            ),
        )
        conexion.commit()
        orden_id = cursor.lastrowid
    finally:
        if conn is None:
            conexion.close()

    return OrdenCompra(
        id=orden_id,
        fecha=fecha_orden,
        proveedor=proveedor,
        estado="aprobada",
        aprobada_por=aprobacion.aprobada_por,
        aprobada_en=aprobacion.aprobada_en,
        items=items,
    )
