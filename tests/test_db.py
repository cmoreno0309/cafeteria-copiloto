"""Pruebas de core/db.py."""

import sqlite3

import pytest

from core.db import get_conn, init_db

TABLAS_ESPERADAS = {
    "insumos",
    "productos",
    "recetas",
    "clientes",
    "ventas",
    "ordenes_compra",
}


@pytest.fixture
def db_path(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    return ruta


def test_init_db_crea_las_seis_tablas(db_path):
    conn = get_conn(db_path)
    filas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()

    nombres = {fila[0] for fila in filas}
    assert TABLAS_ESPERADAS <= nombres


def test_insercion_con_foreign_key_invalida_falla(db_path):
    conn = get_conn(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO recetas (producto_id, insumo_id, cantidad) "
                "VALUES (?, ?, ?)",
                (9999, 9999, 1.0),
            )
    finally:
        conn.close()
