"""Pruebas de core/graph.py: estado, nodo entender y checkpointer."""

import sqlite3
from datetime import date

import pytest

from core.db import init_db
from core.graph import (
    Intencion,
    ParametrosPregunta,
    SalidaEntender,
    _checkpointer,
    construir_grafo,
    entender,
    normalizar_insumo,
)

HOY = date(2026, 8, 13)


@pytest.fixture
def conn_insumos(tmp_path):
    ruta = tmp_path / "cafeteria.db"
    init_db(ruta)
    conexion = sqlite3.connect(ruta)
    conexion.execute(
        "INSERT INTO insumos (nombre, unidad, stock_actual, stock_minimo, "
        "costo_unitario, proveedor) VALUES ('platano', 'kg', 8.5, 3.0, 4.50, "
        "'Mercado de Frutas')"
    )
    conexion.commit()
    yield conexion
    conexion.close()


def test_normalizar_insumo_hace_calzar_tilde_contra_nombre_sin_tilde(conn_insumos):
    assert normalizar_insumo("plátano", conn_insumos) == "platano"


def test_normalizar_insumo_tolera_error_de_tipeo(conn_insumos):
    assert normalizar_insumo("platan", conn_insumos) == "platano"


def test_normalizar_insumo_sin_match_devuelve_el_texto_original(conn_insumos):
    assert normalizar_insumo("kriptonita", conn_insumos) == "kriptonita"


def test_grafo_con_entender_stub_actualiza_estado_y_persiste_checkpoint(
    tmp_path, monkeypatch
):
    salida_canned = SalidaEntender(
        intencion=Intencion(herramientas=["stock_actual"], ambigua=False),
        parametros=ParametrosPregunta(),
    )
    monkeypatch.setattr(
        "core.graph._clasificar", lambda pregunta, hoy=None: salida_canned
    )

    checkpointer = _checkpointer(tmp_path / "checkpoints.db")
    grafo = construir_grafo(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "hilo-de-prueba"}}

    resultado = grafo.invoke(
        {
            "pregunta": "¿Qué insumos están por debajo del mínimo?",
            "intencion": None,
            "parametros": None,
            "resultados_herramientas": {},
            "accion_propuesta": None,
            "aprobacion": None,
            "respuesta": None,
        },
        config=config,
    )

    assert resultado["intencion"] == salida_canned.intencion
    assert resultado["parametros"] == salida_canned.parametros

    estado_persistido = grafo.get_state(config)
    assert estado_persistido.values["intencion"] == salida_canned.intencion


def _estado(pregunta: str) -> dict:
    return {
        "pregunta": pregunta,
        "intencion": None,
        "parametros": None,
        "resultados_herramientas": {},
        "accion_propuesta": None,
        "aprobacion": None,
        "respuesta": None,
    }


@pytest.mark.api
def test_entender_stock_bajo_minimo():
    resultado = entender(_estado("¿Qué insumos están por debajo del mínimo?"))

    assert resultado["intencion"].herramientas == ["stock_actual"]
    assert resultado["intencion"].ambigua is False


@pytest.mark.api
def test_entender_consumo_promedio_normaliza_insumo_con_tilde():
    resultado = entender(_estado("¿Cuál es el consumo promedio diario de plátano?"))

    assert resultado["intencion"].herramientas == ["consumo_promedio"]
    assert resultado["parametros"].insumo == "platano"


@pytest.mark.api
def test_entender_ventas_por_periodo():
    resultado = entender(
        _estado("¿Cómo van las ventas de julio 2026 agrupadas por producto?")
    )

    assert resultado["intencion"].herramientas == ["ventas_por_periodo"]


@pytest.mark.api
def test_entender_margen_por_producto():
    resultado = entender(_estado("¿Cuál producto tuvo mejor margen en julio 2026?"))

    assert resultado["intencion"].herramientas == ["margen_por_producto"]
    assert resultado["parametros"].mes == "2026-07"


@pytest.mark.api
def test_entender_clientes_inactivos():
    resultado = entender(_estado("¿Qué clientes frecuentes dejaron de venir?"))

    assert resultado["intencion"].herramientas == ["clientes_inactivos"]
