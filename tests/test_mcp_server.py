"""Pruebas de channels/mcp_server.py."""

import asyncio
from datetime import date

import pytest

import core.db as db
from core.db import get_conn, init_db

from channels import mcp_server

NOMBRES_ESPERADOS = {
    "stock_actual",
    "consumo_promedio",
    "ventas_por_periodo",
    "margen_por_producto",
    "clientes_inactivos",
    "sugerir_compra",
}


@pytest.fixture
def datos(tmp_path, monkeypatch):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    monkeypatch.setattr(db, "DB_PATH", ruta)

    conexion = get_conn(ruta)
    conexion.executemany(
        "INSERT INTO insumos "
        "(nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("espinaca", "kg", 0.3, 1.0, 2.5, "Verduras Sur"),
            ("platano", "kg", 5.0, 2.0, 1.2, "Frutas del Valle"),
        ],
    )
    conexion.commit()
    conexion.close()


def test_lista_las_6_herramientas_de_lectura_y_excluye_crear_orden_compra(datos):
    tools = asyncio.run(mcp_server.servidor.list_tools())
    nombres = {t.name for t in tools}
    assert nombres == NOMBRES_ESPERADOS
    assert "crear_orden_compra" not in nombres


def test_stock_actual_sin_filtro(datos):
    resultado = mcp_server.stock_actual()
    assert {item["nombre"] for item in resultado["items"]} == {"espinaca", "platano"}


def test_stock_actual_filtra_por_proveedor(datos):
    resultado = mcp_server.stock_actual(proveedor="Frutas del Valle")
    assert [item["nombre"] for item in resultado["items"]] == ["platano"]


def test_consumo_promedio_devuelve_el_insumo_pedido(datos):
    resultado = mcp_server.consumo_promedio(insumo="platano")
    assert resultado["insumo"] == "platano"


def test_consumo_promedio_insumo_inexistente_propaga_value_error(datos):
    with pytest.raises(ValueError):
        mcp_server.consumo_promedio(insumo="no existe")


def test_ventas_por_periodo_sin_ventas_devuelve_totales_en_cero(datos):
    resultado = mcp_server.ventas_por_periodo(
        desde=date(2026, 1, 1), hasta=date(2026, 1, 31), agrupar_por="mes"
    )
    assert resultado["total_ingresos"] == 0
    assert resultado["total_unidades"] == 0


def test_margen_por_producto_sin_ventas_devuelve_lista_vacia(datos):
    resultado = mcp_server.margen_por_producto(mes="2026-01")
    assert resultado["items"] == []


def test_clientes_inactivos_sin_clientes_devuelve_lista_vacia(datos):
    resultado = mcp_server.clientes_inactivos()
    assert resultado["items"] == []


def test_sugerir_compra_devuelve_proveedores(datos):
    resultado = mcp_server.sugerir_compra()
    assert "proveedores" in resultado
