"""Pruebas de core/tools/margen_por_producto.py."""

import pytest

from core.db import get_conn, init_db
from core.tools.margen_por_producto import margen_por_producto


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.execute(
        "INSERT INTO insumos "
        "(id, nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (1, 'leche', 'litro', 20.0, 5.0, 1.0, 'Lacteos Norte')"
    )
    conexion.executemany(
        "INSERT INTO productos (id, nombre, precio_venta, categoria) VALUES (?, ?, ?, ?)",
        [
            (1, "cafe americano", 2.5, "cafe"),  # con receta
            (2, "bowl de acai", 6.0, "bowl"),  # sin receta
            (3, "batido verde", 5.0, "batido"),  # con receta, sin ventas en agosto
        ],
    )
    conexion.executemany(
        "INSERT INTO recetas (producto_id, insumo_id, cantidad) VALUES (?, ?, ?)",
        [
            (1, 1, 0.2),  # costo cafe americano = 0.2 * 1.0 = 0.2
            (3, 1, 0.5),  # costo batido verde = 0.5 * 1.0 = 0.5
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


def test_margen_de_producto_con_receta(conn):
    # precio de catalogo del cafe es 2.5, pero estas ventas quedaron
    # congeladas con precios distintos (subida de precio a mitad de mes).
    _insertar_venta(conn, "2026-08-01", 1, 2, 2.5)
    _insertar_venta(conn, "2026-08-02", 1, 3, 3.0)
    _insertar_venta(conn, "2026-08-03", 2, 1, 6.0)
    conn.commit()

    resultado = margen_por_producto("2026-08", conn=conn)

    cafe = next(i for i in resultado.items if i.producto == "cafe americano")
    assert cafe.precio == pytest.approx(2.5)
    assert cafe.costo == pytest.approx(0.2)
    assert cafe.margen_unitario == pytest.approx(2.3)  # 2.5 - 0.2, teorico de catalogo
    assert cafe.margen_pct == pytest.approx(92.0)  # 2.3 / 2.5 * 100
    assert cafe.unidades_vendidas == 5
    # margen_total real: 2*(2.5-0.2) + 3*(3.0-0.2) = 4.6 + 8.4
    assert cafe.margen_total == pytest.approx(13.0)

    # margen_unitario * unidades_vendidas (11.5) no coincide con margen_total
    # (13.0) porque uno usa precio de catalogo y el otro precio real de
    # venta: es el comportamiento esperado, no un bug.
    assert cafe.margen_unitario * cafe.unidades_vendidas != pytest.approx(cafe.margen_total)

    # orden por margen_total descendente
    assert [i.producto for i in resultado.items] == ["cafe americano", "bowl de acai"]


def test_producto_sin_receta_se_reporta_con_costo_cero(conn):
    _insertar_venta(conn, "2026-08-03", 2, 1, 6.0)
    conn.commit()

    resultado = margen_por_producto("2026-08", conn=conn)

    bowl = next(i for i in resultado.items if i.producto == "bowl de acai")
    assert bowl.costo == 0.0
    assert bowl.margen_unitario == pytest.approx(6.0)
    assert bowl.margen_pct == pytest.approx(100.0)
    assert bowl.margen_total == pytest.approx(6.0)
    assert bowl.unidades_vendidas == 1


def test_solo_incluye_productos_vendidos_en_el_mes(conn):
    # batido verde tiene receta pero ninguna venta en agosto: no aparece.
    _insertar_venta(conn, "2026-08-01", 1, 2, 2.5)
    conn.commit()

    resultado = margen_por_producto("2026-08", conn=conn)

    nombres = [i.producto for i in resultado.items]
    assert "batido verde" not in nombres


def test_mes_sin_ventas_devuelve_lista_vacia(conn):
    _insertar_venta(conn, "2026-08-01", 1, 2, 2.5)
    conn.commit()

    resultado = margen_por_producto("2026-01", conn=conn)

    assert resultado.items == []


def test_formato_de_mes_invalido_lanza_value_error(conn):
    for mes_invalido in ["2026/08", "agosto", "2026-13", "26-08"]:
        with pytest.raises(ValueError):
            margen_por_producto(mes_invalido, conn=conn)
