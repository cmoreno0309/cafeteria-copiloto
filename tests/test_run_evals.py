"""Pruebas de evals/run_evals.py: solo el calculo de costo/tokens (correr
el dataset completo contra Gemini de verdad no es parte de estas pruebas).
"""

from types import SimpleNamespace

from evals.run_evals import _ColectorDeUso, _costo_usd


def test_costo_usd_usa_el_precio_de_gemini_2_5_flash():
    # $0.30/1M entrada, $2.50/1M salida
    costo = _costo_usd(tokens_entrada=1_000_000, tokens_salida=1_000_000)

    assert round(costo, 2) == round(0.30 + 2.50, 2)


def test_costo_usd_con_cero_tokens_es_cero():
    assert _costo_usd(0, 0) == 0.0


def _generacion_falsa(input_tokens: int, output_tokens: int):
    mensaje = SimpleNamespace(
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens}
    )
    return SimpleNamespace(message=mensaje)


def test_colector_de_uso_suma_tokens_de_una_sola_llamada():
    colector = _ColectorDeUso()
    respuesta = SimpleNamespace(generations=[[_generacion_falsa(100, 20)]])

    colector.on_llm_end(respuesta)

    assert colector.tokens_entrada == 100
    assert colector.tokens_salida == 20


def test_colector_de_uso_acumula_entre_varias_llamadas():
    """Una corrida del grafo llama al LLM dos veces (entender + redactar);
    el colector tiene que sumar ambas, no quedarse con la ultima.
    """
    colector = _ColectorDeUso()
    respuesta_1 = SimpleNamespace(generations=[[_generacion_falsa(100, 20)]])
    respuesta_2 = SimpleNamespace(generations=[[_generacion_falsa(300, 50)]])

    colector.on_llm_end(respuesta_1)
    colector.on_llm_end(respuesta_2)

    assert colector.tokens_entrada == 400
    assert colector.tokens_salida == 70


def test_colector_de_uso_ignora_generaciones_sin_usage_metadata():
    colector = _ColectorDeUso()
    sin_uso = SimpleNamespace(message=SimpleNamespace(usage_metadata=None))
    respuesta = SimpleNamespace(generations=[[sin_uso]])

    colector.on_llm_end(respuesta)

    assert colector.tokens_entrada == 0
    assert colector.tokens_salida == 0
