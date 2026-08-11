"""Pruebas de core/tools/consumo_promedio.py."""

from datetime import date, timedelta

import pytest

from core.db import get_conn, init_db
from core.tools.consumo_promedio import consumo_promedio

HOY = date(2026, 8, 11)


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.execute(
        "INSERT INTO insumos "
        "(id, nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (1, 'platano', 'kg', 10.0, 2.0, 1.2, 'Frutas del Valle')"
    )
    conexion.execute(
        "INSERT INTO insumos "
        "(id, nombre, unidad, stock_actual, stock_minimo, costo_unitario, proveedor) "
        "VALUES (2, 'espinaca', 'kg', 5.0, 1.0, 2.5, 'Verduras Sur')"
    )
    conexion.execute(
        "INSERT INTO productos (id, nombre, precio_venta, categoria) "
        "VALUES (1, 'batido de platano', 4.5, 'batido')"
    )
    conexion.execute(
        "INSERT INTO recetas (producto_id, insumo_id, cantidad) VALUES (1, 1, 0.5)"
    )
    conexion.commit()
    yield conexion
    conexion.close()


def _insertar_venta(conn, fecha, cantidad):
    conn.execute(
        "INSERT INTO ventas (fecha, cliente_id, producto_id, cantidad, precio_unitario) "
        "VALUES (?, NULL, 1, ?, 4.5)",
        (fecha, cantidad),
    )


def test_consumo_normal_divide_entre_dias_con_ventas(conn):
    # Ventana de 14 dias terminando en HOY (2026-07-29 a 2026-08-11).
    # Dos domingos sin ventas dentro de la ventana: 2026-08-02 y 2026-08-09.
    dias_ventana = [date(2026, 7, 29) + timedelta(days=i) for i in range(14)]
    domingos = {date(2026, 8, 2), date(2026, 8, 9)}
    dias_con_venta = [d for d in dias_ventana if d not in domingos]

    for d in dias_con_venta:
        _insertar_venta(conn, d.isoformat(), 4)  # 4 batidos -> 2.0 kg de platano
    conn.commit()

    resultado = consumo_promedio("platano", dias=14, conn=conn, hoy=HOY)

    assert resultado.dias_analizados == 14
    assert resultado.dias_con_ventas == 12
    consumo_total = 12 * 4 * 0.5  # 24.0 kg
    consumo_diario_esperado = consumo_total / 12
    assert resultado.consumo_diario == pytest.approx(consumo_diario_esperado)
    assert resultado.dias_de_cobertura == pytest.approx(10.0 / consumo_diario_esperado)


def test_insumo_sin_ventas_en_la_ventana(conn):
    resultado = consumo_promedio("espinaca", dias=14, conn=conn, hoy=HOY)

    assert resultado.consumo_diario == 0.0
    assert resultado.dias_de_cobertura is None


def test_insumo_inexistente_lanza_value_error_con_sugerencia(conn):
    with pytest.raises(ValueError, match="platano"):
        consumo_promedio("platanoo", dias=14, conn=conn, hoy=HOY)


def test_ventana_mas_corta_que_los_datos_disponibles(conn):
    # Ventas en un rango amplio; solo deben contar las de los ultimos 5 dias.
    for i in range(20):
        fecha = date(2026, 8, 11) - timedelta(days=i)
        if fecha.weekday() != 6:
            _insertar_venta(conn, fecha.isoformat(), 2)
    conn.commit()

    resultado = consumo_promedio("platano", dias=5, conn=conn, hoy=HOY)

    # Ventana: 2026-08-07 a 2026-08-11, con un domingo (2026-08-09) sin ventas.
    assert resultado.dias_analizados == 5
    assert resultado.dias_con_ventas == 4
    consumo_diario_esperado = (4 * 2 * 0.5) / 4
    assert resultado.consumo_diario == pytest.approx(consumo_diario_esperado)
