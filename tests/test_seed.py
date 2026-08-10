"""Pruebas de scripts/seed.py."""

from datetime import date, timedelta

import pytest

from core.db import get_conn, init_db
from scripts.seed import (
    DIAS_HISTORIA,
    NUM_CLIENTES,
    NUM_CLIENTES_INACTIVOS,
    PRODUCTO_EN_DECLIVE,
    poblar,
)

HOY = date(2026, 8, 10)


@pytest.fixture
def conn(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    poblar(conexion, hoy=HOY)
    yield conexion
    conexion.close()


def test_carga_12_insumos(conn):
    (total,) = conn.execute("SELECT COUNT(*) FROM insumos").fetchone()
    assert total == 12


def test_carga_10_productos(conn):
    (total,) = conn.execute("SELECT COUNT(*) FROM productos").fetchone()
    assert total == 10


def test_carga_recetas_de_todos_los_productos(conn):
    (total,) = conn.execute("SELECT COUNT(DISTINCT producto_id) FROM recetas").fetchone()
    assert total == 10


def test_genera_25_clientes(conn):
    (total,) = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()
    assert total == NUM_CLIENTES


def test_ventas_cubren_60_dias_hasta_hoy(conn):
    fecha_min, fecha_max = conn.execute(
        "SELECT MIN(fecha), MAX(fecha) FROM ventas"
    ).fetchone()
    assert fecha_max == HOY.isoformat()
    assert fecha_min == (HOY - timedelta(days=DIAS_HISTORIA - 1)).isoformat()


def test_viernes_y_sabado_venden_mas_que_lunes(conn):
    filas = conn.execute(
        "SELECT fecha, SUM(cantidad) FROM ventas GROUP BY fecha"
    ).fetchall()
    por_dia_semana = {}
    for fecha_texto, unidades in filas:
        dia_semana = date.fromisoformat(fecha_texto).weekday()
        por_dia_semana.setdefault(dia_semana, []).append(unidades)

    promedio_lunes = sum(por_dia_semana[0]) / len(por_dia_semana[0])
    promedio_viernes = sum(por_dia_semana[4]) / len(por_dia_semana[4])
    promedio_sabado = sum(por_dia_semana[5]) / len(por_dia_semana[5])

    assert promedio_viernes > promedio_lunes
    assert promedio_sabado > promedio_lunes


def test_hay_5_clientes_inactivos_hace_mas_de_30_dias(conn):
    limite = (HOY - timedelta(days=30)).isoformat()
    filas = conn.execute(
        """
        SELECT cliente_id
        FROM ventas
        WHERE cliente_id IS NOT NULL
        GROUP BY cliente_id
        HAVING COUNT(*) >= 3 AND MAX(fecha) < ?
        """,
        (limite,),
    ).fetchall()
    assert len(filas) == NUM_CLIENTES_INACTIVOS


def test_producto_en_declive_vende_menos_en_el_segundo_tramo(conn):
    mitad = (HOY - timedelta(days=DIAS_HISTORIA // 2)).isoformat()
    (unidades_antes,) = conn.execute(
        """
        SELECT COALESCE(SUM(v.cantidad), 0)
        FROM ventas v JOIN productos p ON p.id = v.producto_id
        WHERE p.nombre = ? AND v.fecha < ?
        """,
        (PRODUCTO_EN_DECLIVE, mitad),
    ).fetchone()
    (unidades_despues,) = conn.execute(
        """
        SELECT COALESCE(SUM(v.cantidad), 0)
        FROM ventas v JOIN productos p ON p.id = v.producto_id
        WHERE p.nombre = ? AND v.fecha >= ?
        """,
        (PRODUCTO_EN_DECLIVE, mitad),
    ).fetchone()
    assert unidades_antes > unidades_despues


def test_poblar_es_repetible(conn):
    poblar(conn, hoy=HOY)
    (total,) = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()
    assert total == NUM_CLIENTES
