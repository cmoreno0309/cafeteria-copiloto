"""Pruebas de core/tools/ventas_por_periodo.py."""

from datetime import date

import pytest

from core.db import get_conn, init_db
from core.models import FilaVenta
from core.tools.ventas_por_periodo import ventas_por_periodo


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.executemany(
        "INSERT INTO productos (id, nombre, precio_venta, categoria) VALUES (?, ?, ?, ?)",
        [
            (1, "cafe americano", 2.5, "cafe"),
            (2, "bowl de acai", 6.0, "bowl"),
            (3, "batido verde", 5.0, "batido"),
        ],
    )
    conexion.commit()
    yield conexion
    conexion.close()


def _insertar_venta(conn, fecha, producto_id, cantidad, precio_unitario):
    conn.execute(
        "INSERT INTO ventas (fecha, cliente_id, producto_id, cantidad, precio_unitario) "
        "VALUES (?, NULL, ?, ?, ?)",
        (fecha, producto_id, cantidad, precio_unitario),
    )


def test_agrupa_por_dia(conn):
    _insertar_venta(conn, "2026-07-27", 1, 2, 2.5)  # 5.0
    _insertar_venta(conn, "2026-07-28", 1, 3, 2.5)  # 7.5
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 27), date(2026, 7, 28), "dia", conn=conn
    )

    assert resultado.total_ingresos == pytest.approx(12.5)
    assert resultado.total_unidades == 5
    assert resultado.filas == [
        FilaVenta(etiqueta="2026-07-27", ingresos=5.0, unidades=2),
        FilaVenta(etiqueta="2026-07-28", ingresos=7.5, unidades=3),
    ]


def test_agrupa_por_semana(conn):
    # 2026-07-27 es lunes; su semana va hasta 2026-08-02 (domingo).
    # 2026-08-03 es el lunes siguiente.
    _insertar_venta(conn, "2026-07-28", 1, 2, 2.5)  # semana del 2026-07-27: 5.0
    _insertar_venta(conn, "2026-08-04", 1, 4, 2.5)  # semana del 2026-08-03: 10.0
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 27), date(2026, 8, 9), "semana", conn=conn
    )

    assert resultado.total_ingresos == pytest.approx(15.0)
    assert resultado.total_unidades == 6
    assert resultado.filas == [
        FilaVenta(etiqueta="2026-07-27", ingresos=5.0, unidades=2),
        FilaVenta(etiqueta="2026-08-03", ingresos=10.0, unidades=4),
    ]


def test_agrupa_por_mes(conn):
    _insertar_venta(conn, "2026-07-15", 1, 2, 2.5)  # 5.0
    _insertar_venta(conn, "2026-08-05", 1, 3, 2.5)  # 7.5
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 1), date(2026, 8, 31), "mes", conn=conn
    )

    assert resultado.total_ingresos == pytest.approx(12.5)
    assert resultado.total_unidades == 5
    assert resultado.filas == [
        FilaVenta(etiqueta="2026-07", ingresos=5.0, unidades=2),
        FilaVenta(etiqueta="2026-08", ingresos=7.5, unidades=3),
    ]


def test_agrupa_por_producto(conn):
    _insertar_venta(conn, "2026-07-01", 1, 2, 2.5)  # cafe americano: 5.0
    _insertar_venta(conn, "2026-07-02", 2, 1, 6.0)  # bowl de acai: 6.0
    _insertar_venta(conn, "2026-07-03", 3, 3, 5.0)  # batido verde: 15.0
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 1), date(2026, 7, 3), "producto", conn=conn
    )

    assert resultado.total_ingresos == pytest.approx(26.0)
    assert resultado.total_unidades == 6
    # ordenado por ingresos descendente
    assert resultado.filas == [
        FilaVenta(etiqueta="batido verde", ingresos=15.0, unidades=3),
        FilaVenta(etiqueta="bowl de acai", ingresos=6.0, unidades=1),
        FilaVenta(etiqueta="cafe americano", ingresos=5.0, unidades=2),
    ]


def test_agrupa_por_categoria(conn):
    _insertar_venta(conn, "2026-07-01", 1, 2, 2.5)  # cafe: 5.0
    _insertar_venta(conn, "2026-07-02", 2, 1, 6.0)  # bowl: 6.0
    _insertar_venta(conn, "2026-07-03", 3, 3, 5.0)  # batido: 15.0
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 1), date(2026, 7, 3), "categoria", conn=conn
    )

    assert resultado.total_ingresos == pytest.approx(26.0)
    assert resultado.total_unidades == 6
    assert resultado.filas == [
        FilaVenta(etiqueta="batido", ingresos=15.0, unidades=3),
        FilaVenta(etiqueta="bowl", ingresos=6.0, unidades=1),
        FilaVenta(etiqueta="cafe", ingresos=5.0, unidades=2),
    ]


def test_ingresos_usan_precio_unitario_de_la_venta_no_del_catalogo(conn):
    # cafe americano tiene precio_venta=2.5 en productos, pero estas dos
    # ventas quedaron congeladas con precios distintos (simula un cambio
    # de precio entre una venta y otra).
    _insertar_venta(conn, "2026-07-01", 1, 2, 2.0)  # 2 x 2.0 = 4.0
    _insertar_venta(conn, "2026-07-02", 1, 1, 3.0)  # 1 x 3.0 = 3.0
    conn.commit()

    resultado = ventas_por_periodo(
        date(2026, 7, 1), date(2026, 7, 2), "producto", conn=conn
    )

    # 7.0 (precios reales de la venta), no 7.5 (3 unidades x 2.5 del catalogo)
    assert resultado.total_ingresos == pytest.approx(7.0)
    assert resultado.filas == [
        FilaVenta(etiqueta="cafe americano", ingresos=7.0, unidades=3),
    ]


def test_rango_sin_ventas_totales_en_cero_y_filas_vacia(conn):
    _insertar_venta(conn, "2026-07-01", 1, 2, 2.5)
    conn.commit()

    resultado = ventas_por_periodo(
        date(2030, 1, 1), date(2030, 1, 31), "dia", conn=conn
    )

    assert resultado.total_ingresos == 0
    assert resultado.total_unidades == 0
    assert resultado.filas == []


def test_agrupar_por_invalido_lanza_value_error(conn):
    with pytest.raises(ValueError):
        ventas_por_periodo(
            date(2026, 7, 1), date(2026, 7, 31), "año", conn=conn
        )


def test_desde_posterior_a_hasta_lanza_value_error(conn):
    with pytest.raises(ValueError):
        ventas_por_periodo(
            date(2026, 8, 10), date(2026, 8, 1), "dia", conn=conn
        )
