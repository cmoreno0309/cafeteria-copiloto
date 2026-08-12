"""Pruebas de core/tools/crear_orden_compra.py."""

import json
from datetime import date, datetime

import pytest

from core.db import get_conn, init_db
from core.models import Aprobacion, ItemOrden
from core.tools.crear_orden_compra import crear_orden_compra

HOY = date(2026, 8, 11)


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    yield conexion
    conexion.close()


def _contar_ordenes(conn):
    (total,) = conn.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()
    return total


def test_sin_aprobacion_lanza_excepcion_y_no_inserta(conn):
    items = [ItemOrden(insumo="leche", cantidad=10.0, unidad="litro")]

    with pytest.raises(PermissionError):
        crear_orden_compra("Lacteos Norte", items, conn=conn, hoy=HOY)

    assert _contar_ordenes(conn) == 0


def test_con_aprobacion_inserta_y_detalle_json_se_reconstruye(conn):
    items = [
        ItemOrden(insumo="leche", cantidad=10.0, unidad="litro"),
        ItemOrden(insumo="platano", cantidad=3.5, unidad="kg"),
    ]
    aprobacion = Aprobacion(aprobada_por="dueña", aprobada_en=datetime(2026, 8, 11, 9, 30))

    resultado = crear_orden_compra(
        "Lacteos Norte", items, aprobacion=aprobacion, conn=conn, hoy=HOY
    )

    assert _contar_ordenes(conn) == 1
    assert resultado.estado == "aprobada"
    assert resultado.proveedor == "Lacteos Norte"
    assert resultado.aprobada_por == "dueña"
    assert resultado.aprobada_en == datetime(2026, 8, 11, 9, 30)
    assert resultado.fecha == HOY

    (detalle_json,) = conn.execute(
        "SELECT detalle_json FROM ordenes_compra WHERE id = ?", (resultado.id,)
    ).fetchone()
    items_reconstruidos = [ItemOrden(**item) for item in json.loads(detalle_json)]
    assert items_reconstruidos == items


def test_proveedor_vacio_lanza_value_error_y_no_inserta(conn):
    items = [ItemOrden(insumo="leche", cantidad=10.0, unidad="litro")]
    aprobacion = Aprobacion(aprobada_por="dueña", aprobada_en=datetime(2026, 8, 11, 9, 30))

    with pytest.raises(ValueError):
        crear_orden_compra("", items, aprobacion=aprobacion, conn=conn, hoy=HOY)

    assert _contar_ordenes(conn) == 0


def test_items_vacia_lanza_value_error_y_no_inserta(conn):
    aprobacion = Aprobacion(aprobada_por="dueña", aprobada_en=datetime(2026, 8, 11, 9, 30))

    with pytest.raises(ValueError):
        crear_orden_compra("Lacteos Norte", [], aprobacion=aprobacion, conn=conn, hoy=HOY)

    assert _contar_ordenes(conn) == 0


def test_dos_ordenes_en_la_misma_sesion_quedan_como_filas_independientes(conn):
    items_1 = [ItemOrden(insumo="leche", cantidad=10.0, unidad="litro")]
    items_2 = [ItemOrden(insumo="platano", cantidad=3.5, unidad="kg")]
    aprobacion_1 = Aprobacion(aprobada_por="dueña", aprobada_en=datetime(2026, 8, 11, 9, 30))
    aprobacion_2 = Aprobacion(aprobada_por="encargado", aprobada_en=datetime(2026, 8, 11, 15, 0))

    orden_1 = crear_orden_compra(
        "Lacteos Norte", items_1, aprobacion=aprobacion_1, conn=conn, hoy=HOY
    )
    orden_2 = crear_orden_compra(
        "Frutas del Valle", items_2, aprobacion=aprobacion_2, conn=conn, hoy=HOY
    )

    assert _contar_ordenes(conn) == 2
    assert orden_1.id != orden_2.id
    assert orden_1.proveedor == "Lacteos Norte"
    assert orden_2.proveedor == "Frutas del Valle"
    assert orden_1.aprobada_por == "dueña"
    assert orden_2.aprobada_por == "encargado"
