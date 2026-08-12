"""Pruebas de core/tools/sugerir_compra.py."""

from datetime import date

import pytest

from core.db import get_conn, init_db
from core.tools.sugerir_compra import _cantidad_a_comprar, sugerir_compra

HOY = date(2026, 8, 11)


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    yield conexion
    conexion.close()


def _insertar_insumo(conn, insumo_id, producto_id, nombre, stock, costo_unitario, proveedor):
    conn.execute(
        "INSERT INTO insumos "
        "(id, nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (?, ?, 'kg', ?, 1.0, ?, ?)",
        (insumo_id, nombre, stock, costo_unitario, proveedor),
    )
    conn.execute(
        "INSERT INTO productos (id, nombre, precio_venta, categoria) "
        "VALUES (?, ?, 1.0, 'insumo_test')",
        (producto_id, f"producto de {nombre}"),
    )
    conn.execute(
        "INSERT INTO recetas (producto_id, insumo_id, cantidad) VALUES (?, ?, 1.0)",
        (producto_id, insumo_id),
    )


def _insertar_venta(conn, fecha, producto_id, cantidad):
    conn.execute(
        "INSERT INTO ventas (fecha, cliente_id, producto_id, cantidad, precio_unitario) "
        "VALUES (?, NULL, ?, ?, 1.0)",
        (fecha, producto_id, cantidad),
    )


def test_cobertura_menor_a_3_es_urgente(conn):
    _insertar_insumo(conn, 1, 1, "zanahoria", stock=4.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 4)  # consumo_diario=4 -> cobertura=1
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    items = resultado.proveedores[0].items
    assert len(items) == 1
    assert items[0].insumo == "zanahoria"
    assert items[0].urgencia == "urgente"
    assert items[0].cantidad == 52  # ceil(4*14 - 4)
    assert items[0].costo_unitario_estimado == pytest.approx(1.0)


def test_cobertura_exactamente_3_es_esta_semana(conn):
    _insertar_insumo(conn, 1, 1, "leche", stock=6.0, costo_unitario=2.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 2)  # consumo_diario=2 -> cobertura=3

    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    items = resultado.proveedores[0].items
    assert items[0].urgencia == "esta_semana"
    assert items[0].cantidad == 22  # ceil(2*14 - 6)


def test_cobertura_exactamente_7_queda_excluida(conn):
    _insertar_insumo(conn, 1, 1, "avena", stock=14.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 2)  # consumo_diario=2 -> cobertura=7
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    assert resultado.proveedores == []


def test_cobertura_entre_3_y_7_es_esta_semana(conn):
    _insertar_insumo(conn, 1, 1, "platano", stock=10.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 2)  # consumo_diario=2 -> cobertura=5
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    items = resultado.proveedores[0].items
    assert items[0].urgencia == "esta_semana"
    assert items[0].cantidad == 18  # ceil(2*14 - 10)


def test_cobertura_mayor_o_igual_a_7_queda_excluida(conn):
    _insertar_insumo(conn, 1, 1, "espinaca", stock=20.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 2)  # consumo_diario=2 -> cobertura=10
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    assert resultado.proveedores == []


def test_consumo_diario_cero_queda_excluida_sin_error(conn):
    _insertar_insumo(conn, 1, 1, "canela", stock=0.5, costo_unitario=5.0, proveedor="Proveedor A")
    # sin ventas: consumo_diario = 0, dias_de_cobertura = None
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    assert resultado.proveedores == []


def test_ningun_insumo_necesita_compra_devuelve_vacio(conn):
    _insertar_insumo(conn, 1, 1, "sal", stock=100.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 1)  # cobertura=100, muy por encima de 7
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    assert resultado.proveedores == []


def test_agrupa_por_proveedor(conn):
    # dos insumos del mismo proveedor, ambos califican
    _insertar_insumo(conn, 1, 1, "harina", stock=4.0, costo_unitario=1.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 1, 4)  # cobertura=1, urgente
    _insertar_insumo(conn, 2, 2, "azucar", stock=6.0, costo_unitario=2.0, proveedor="Proveedor A")
    _insertar_venta(conn, HOY.isoformat(), 2, 2)  # cobertura=3, esta_semana
    # un insumo de otro proveedor, tambien califica
    _insertar_insumo(conn, 3, 3, "cafe", stock=10.0, costo_unitario=3.0, proveedor="Proveedor B")
    _insertar_venta(conn, HOY.isoformat(), 3, 2)  # cobertura=5, esta_semana
    conn.commit()

    resultado = sugerir_compra(conn=conn, hoy=HOY)

    proveedores = {p.proveedor: p.items for p in resultado.proveedores}
    assert set(proveedores.keys()) == {"Proveedor A", "Proveedor B"}
    assert len(proveedores["Proveedor A"]) == 2
    assert len(proveedores["Proveedor B"]) == 1
    assert {i.insumo for i in proveedores["Proveedor A"]} == {"harina", "azucar"}


def test_cantidad_a_comprar_no_positiva_se_detecta():
    # Estos valores no ocurren en la practica bajo cobertura < 7 (ver docstring),
    # pero la funcion auxiliar debe seguir devolviendo un valor <= 0 detectable
    # por quien la llama, como red de seguridad ante imprecision de punto flotante.
    assert _cantidad_a_comprar(consumo_diario=1.0, stock=14.0) <= 0  # exactamente cero
    assert _cantidad_a_comprar(consumo_diario=1.0, stock=20.0) <= 0  # negativo
