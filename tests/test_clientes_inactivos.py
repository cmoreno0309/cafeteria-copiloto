"""Pruebas de core/tools/clientes_inactivos.py."""

from datetime import date, timedelta

import pytest

from core.db import get_conn, init_db
from core.tools.clientes_inactivos import clientes_inactivos

HOY = date(2026, 8, 11)


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.execute(
        "INSERT INTO productos (id, nombre, precio_venta, categoria) "
        "VALUES (1, 'cafe americano', 2.5, 'cafe')"
    )
    conexion.executemany(
        "INSERT INTO clientes (id, nombre, fecha_registro) VALUES (?, ?, ?)",
        [
            (1, "Ana", "2026-01-01"),
            (2, "Beto", "2026-01-01"),
            (3, "Caro", "2026-01-01"),
            (4, "Dani", "2026-01-01"),
        ],
    )
    conexion.commit()
    yield conexion
    conexion.close()


def _insertar_venta(conn, fecha, cliente_id, cantidad=1, precio_unitario=2.5):
    conn.execute(
        "INSERT INTO ventas (fecha, cliente_id, producto_id, cantidad, precio_unitario) "
        "VALUES (?, ?, 1, ?, ?)",
        (fecha, cliente_id, cantidad, precio_unitario),
    )


def _fecha(dias_atras):
    return (HOY - timedelta(days=dias_atras)).isoformat()


def test_cliente_con_exactamente_minimo_compras_entra(conn):
    # Ana: exactamente 3 compras (minimo_compras), todas viejas.
    for i in range(3):
        _insertar_venta(conn, _fecha(30 + i), cliente_id=1)
    # Beto: solo 2 compras (minimo_compras - 1), tambien viejas.
    for i in range(2):
        _insertar_venta(conn, _fecha(30 + i), cliente_id=2)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    nombres = [i.nombre for i in resultado.items]
    assert "Ana" in nombres
    assert "Beto" not in nombres


def test_ultima_compra_hace_exactamente_dias_cuenta_como_inactivo(conn):
    # Caro: 3 compras, la ultima hace EXACTAMENTE 21 dias -> frontera inclusiva.
    _insertar_venta(conn, _fecha(40), cliente_id=3)
    _insertar_venta(conn, _fecha(30), cliente_id=3)
    _insertar_venta(conn, _fecha(21), cliente_id=3)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    caro = next(i for i in resultado.items if i.nombre == "Caro")
    assert caro.dias_sin_venir == 21


def test_ultima_compra_hace_dias_menos_uno_no_cuenta_como_inactivo(conn):
    # Dani: 3 compras, la ultima hace 20 dias (dias - 1) -> todavia activo.
    _insertar_venta(conn, _fecha(40), cliente_id=4)
    _insertar_venta(conn, _fecha(30), cliente_id=4)
    _insertar_venta(conn, _fecha(20), cliente_id=4)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    nombres = [i.nombre for i in resultado.items]
    assert "Dani" not in nombres


def test_ventas_con_cliente_id_null_se_ignoran(conn):
    # Ventas anonimas: no deben crear un cliente fantasma ni sumarse a nadie.
    for i in range(5):
        _insertar_venta(conn, _fecha(30 + i), cliente_id=None)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    assert resultado.items == []


def test_ningun_cliente_inactivo_devuelve_lista_vacia(conn):
    # Ana compra seguido, dentro de la ventana de 21 dias.
    for i in range(3):
        _insertar_venta(conn, _fecha(i), cliente_id=1)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    assert resultado.items == []


def test_compras_totales_y_ticket_promedio(conn):
    _insertar_venta(conn, _fecha(40), cliente_id=1, cantidad=2, precio_unitario=2.5)
    _insertar_venta(conn, _fecha(35), cliente_id=1, cantidad=1, precio_unitario=3.0)
    _insertar_venta(conn, _fecha(30), cliente_id=1, cantidad=4, precio_unitario=2.0)
    conn.commit()

    resultado = clientes_inactivos(dias=21, minimo_compras=3, conn=conn, hoy=HOY)

    ana = next(i for i in resultado.items if i.nombre == "Ana")
    assert ana.compras_totales == 3
    assert ana.ultima_compra == HOY - timedelta(days=30)
    # tickets: 2*2.5=5.0, 1*3.0=3.0, 4*2.0=8.0 -> promedio = 16/3
    assert ana.ticket_promedio == pytest.approx(16 / 3)
