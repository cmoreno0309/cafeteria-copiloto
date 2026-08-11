"""Pruebas de core/tools/stock_actual.py."""

import pytest

from core.db import get_conn, init_db
from core.tools.stock_actual import stock_actual


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.executemany(
        "INSERT INTO insumos "
        "(nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("espinaca", "kg", 0.3, 1.0, 2.5, "Verduras Sur"),
            ("platano", "kg", 5.0, 2.0, 1.2, "Frutas del Valle"),
            ("leche", "litro", 3.0, 3.0, 1.0, "Lacteos Norte"),
        ],
    )
    conexion.commit()
    yield conexion
    conexion.close()


def test_sin_filtro_devuelve_todos_los_insumos(conn):
    resultado = stock_actual(conn=conn)
    assert len(resultado.items) == 3


def test_filtra_por_proveedor(conn):
    resultado = stock_actual(proveedor="Frutas del Valle", conn=conn)
    assert len(resultado.items) == 1
    assert resultado.items[0].nombre == "platano"


def test_proveedor_inexistente_devuelve_lista_vacia(conn):
    resultado = stock_actual(proveedor="Proveedor Fantasma", conn=conn)
    assert resultado.items == []


def test_bajo_minimo_true_cuando_stock_menor_que_minimo(conn):
    resultado = stock_actual(proveedor="Verduras Sur", conn=conn)
    assert resultado.items[0].bajo_minimo is True


def test_bajo_minimo_false_cuando_stock_igual_al_minimo(conn):
    resultado = stock_actual(proveedor="Lacteos Norte", conn=conn)
    assert resultado.items[0].bajo_minimo is False
