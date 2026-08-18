"""Pruebas de evals/costo_langfuse.py (solo la agregacion pura: consultar
la API real de Langfuse no es parte de estas pruebas, ver tests/test_tracing.py
para lo que si se prueba sin un servidor vivo).
"""

from dataclasses import dataclass

from evals.costo_langfuse import _agregar


@dataclass
class _TrazaFalsa:
    total_cost: float | None
    latency: float | None


def test_agregar_sin_trazas_devuelve_ceros():
    assert _agregar([]) == (0.0, 0.0, None)


def test_agregar_suma_costo_y_promedia_latencia():
    trazas = [
        _TrazaFalsa(total_cost=0.001, latency=1.0),
        _TrazaFalsa(total_cost=0.002, latency=3.0),
    ]

    costo_total, costo_promedio, latencia_promedio = _agregar(trazas)

    assert costo_total == 0.003
    assert costo_promedio == 0.0015
    assert latencia_promedio == 2.0


def test_agregar_trata_costo_none_como_cero():
    trazas = [
        _TrazaFalsa(total_cost=0.004, latency=2.0),
        _TrazaFalsa(total_cost=None, latency=None),
    ]

    costo_total, costo_promedio, latencia_promedio = _agregar(trazas)

    assert costo_total == 0.004
    assert costo_promedio == 0.002
    assert latencia_promedio == 2.0
