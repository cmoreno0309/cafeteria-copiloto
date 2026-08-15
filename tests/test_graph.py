"""Pruebas de core/graph.py: estado, nodo entender y checkpointer."""

import re
import sqlite3
from datetime import date

import pytest

from core.db import get_conn, init_db
from core.graph import (
    ErrorHerramienta,
    Intencion,
    ParametrosPregunta,
    ResultadoHerramienta,
    SalidaEntender,
    SalidaRedactar,
    _checkpointer,
    construir_grafo,
    ejecutar_herramientas,
    entender,
    normalizar_insumo,
    redactar,
)
from core.models import (
    ConsumoInsumo,
    ItemStock,
    ListaClientes,
    ListaMargenes,
    ListaStock,
    ListaSugerencias,
    ResumenVentas,
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
    monkeypatch.setattr(
        "core.graph._generar_respuesta",
        lambda pregunta, resultados: SalidaRedactar(respuesta="respuesta de prueba"),
    )

    checkpointer = _checkpointer(tmp_path / "checkpoints.db")
    grafo = construir_grafo(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "hilo-de-prueba"}}

    resultado = grafo.invoke(
        {
            "pregunta": "¿Qué insumos están por debajo del mínimo?",
            "intencion": None,
            "parametros": None,
            "resultados_herramientas": [],
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


@pytest.fixture
def conn_stock(tmp_path):
    ruta = tmp_path / "test.db"
    init_db(ruta)
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
    yield conexion
    conexion.close()


def _estado_con(intencion: Intencion, parametros: ParametrosPregunta | None = None) -> dict:
    estado = _estado("pregunta de prueba")
    estado["intencion"] = intencion
    estado["parametros"] = parametros
    return estado


def _por_herramienta(
    resultados: list[ResultadoHerramienta], nombre: str
) -> list[ResultadoHerramienta]:
    """Todas las entradas de la lista que corresponden a `nombre`.

    Puede haber mas de una (ej. ventas_por_periodo llamado dos veces para
    comparar periodos), por eso devuelve una lista, no una sola entrada.
    """
    return [entrada for entrada in resultados if entrada.herramienta == nombre]


def test_ejecutar_herramientas_llama_stock_actual_con_parametros_correctos(
    conn_stock,
):
    estado = _estado_con(
        Intencion(herramientas=["stock_actual"], ambigua=False),
        ParametrosPregunta(proveedor="Frutas del Valle"),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    (entrada,) = _por_herramienta(resultado["resultados_herramientas"], "stock_actual")
    items = entrada.resultado.items
    assert len(items) == 1
    assert items[0].nombre == "platano"


def test_ejecutar_herramientas_registra_value_error_como_error_herramienta(
    conn_stock,
):
    estado = _estado_con(
        Intencion(herramientas=["consumo_promedio"], ambigua=False),
        ParametrosPregunta(insumo="insumo que no existe"),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    (entrada,) = _por_herramienta(
        resultado["resultados_herramientas"], "consumo_promedio"
    )
    assert isinstance(entrada.resultado, ErrorHerramienta)
    assert "no existe" in entrada.resultado.mensaje


def test_ejecutar_herramientas_pregunta_ambigua_no_llama_ninguna_herramienta(
    conn_stock,
):
    estado = _estado_con(
        Intencion(herramientas=[], ambigua=True, motivo="falta el periodo"),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    assert resultado["resultados_herramientas"] == []


def test_ejecutar_herramientas_sin_intencion_no_llama_ninguna_herramienta(conn_stock):
    estado = _estado("pregunta de prueba")

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    assert resultado["resultados_herramientas"] == []


@pytest.fixture
def conn_ventas(tmp_path):
    ruta = tmp_path / "ventas.db"
    init_db(ruta)
    conexion = get_conn(ruta)
    conexion.execute(
        "INSERT INTO productos (nombre, categoria, precio_venta) "
        "VALUES ('cafe', 'bebida', 2.0)"
    )
    conexion.executemany(
        "INSERT INTO ventas (producto_id, cantidad, precio_unitario, fecha) "
        "VALUES (1, ?, 2.0, ?)",
        [
            (10, "2026-07-15"),
            (5, "2026-06-15"),
        ],
    )
    conexion.commit()
    yield conexion
    conexion.close()


def test_ejecutar_herramientas_compara_dos_periodos_de_ventas(conn_ventas):
    estado = _estado_con(
        Intencion(herramientas=["ventas_por_periodo"], ambigua=False),
        ParametrosPregunta(
            desde=date(2026, 7, 1),
            hasta=date(2026, 7, 31),
            desde_comparacion=date(2026, 6, 1),
            hasta_comparacion=date(2026, 6, 30),
            agrupar_por="dia",
        ),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_ventas)

    entradas = _por_herramienta(resultado["resultados_herramientas"], "ventas_por_periodo")
    assert len(entradas) == 2
    assert entradas[0].parametros["desde"] == date(2026, 7, 1)
    assert entradas[0].resultado.total_unidades == 10
    assert entradas[1].parametros["desde"] == date(2026, 6, 1)
    assert entradas[1].resultado.total_unidades == 5


def test_ejecutar_herramientas_error_en_periodo_de_comparacion_no_afecta_al_principal(
    conn_ventas,
):
    estado = _estado_con(
        Intencion(herramientas=["ventas_por_periodo"], ambigua=False),
        ParametrosPregunta(
            desde=date(2026, 7, 1),
            hasta=date(2026, 7, 31),
            desde_comparacion=date(2026, 6, 30),
            hasta_comparacion=date(2026, 6, 1),
            agrupar_por="dia",
        ),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_ventas)

    entradas = _por_herramienta(resultado["resultados_herramientas"], "ventas_por_periodo")
    assert len(entradas) == 2
    assert entradas[0].resultado.total_unidades == 10
    assert isinstance(entradas[1].resultado, ErrorHerramienta)


def test_ejecutar_herramientas_consumo_promedio_sin_insumo_da_error_claro(conn_stock):
    """Si la pregunta no menciona que insumo, no hay default posible: debe
    quedar como ErrorHerramienta explicito, no como 'el insumo None no
    existe' (el mensaje crudo que da la herramienta con insumo=None).
    """
    estado = _estado_con(
        Intencion(herramientas=["consumo_promedio"], ambigua=False),
        ParametrosPregunta(),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    (entrada,) = _por_herramienta(resultado["resultados_herramientas"], "consumo_promedio")
    assert isinstance(entrada.resultado, ErrorHerramienta)
    assert "insumo" in entrada.resultado.mensaje


def test_ejecutar_herramientas_ventas_por_periodo_sin_fechas_no_crashea(conn_stock):
    """Antes de validar en el kwargs builder, desde/hasta en None llegaban
    a la herramienta y 'desde > hasta' con None crasheaba con TypeError sin
    que el except ValueError lo atajara.
    """
    estado = _estado_con(
        Intencion(herramientas=["ventas_por_periodo"], ambigua=False),
        ParametrosPregunta(agrupar_por="mes"),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    (entrada,) = _por_herramienta(
        resultado["resultados_herramientas"], "ventas_por_periodo"
    )
    assert isinstance(entrada.resultado, ErrorHerramienta)
    assert "periodo" in entrada.resultado.mensaje


def test_ejecutar_herramientas_margen_sin_mes_no_devuelve_vacio_silencioso(conn_stock):
    """Sin la validacion, mes=None no levanta error en margen_por_producto:
    la comparacion SQL contra NULL no matchea nada y devuelve una lista
    vacia que parece (incorrectamente) 'sin margenes ese mes'.
    """
    estado = _estado_con(
        Intencion(herramientas=["margen_por_producto"], ambigua=False),
        ParametrosPregunta(),
    )

    resultado = ejecutar_herramientas(estado, conn=conn_stock)

    (entrada,) = _por_herramienta(
        resultado["resultados_herramientas"], "margen_por_producto"
    )
    assert isinstance(entrada.resultado, ErrorHerramienta)
    assert "mes" in entrada.resultado.mensaje


def test_redactar_pregunta_ambigua_usa_el_motivo_sin_llamar_al_llm(monkeypatch):
    def _fallar_si_se_llama(pregunta, resultados):
        raise AssertionError(
            "redactar no deberia llamar al LLM cuando la intencion es ambigua"
        )

    monkeypatch.setattr("core.graph._generar_respuesta", _fallar_si_se_llama)

    estado = _estado_con(
        Intencion(herramientas=[], ambigua=True, motivo="¿de que insumo hablas?")
    )

    resultado = redactar(estado)

    assert resultado["respuesta"] == "¿de que insumo hablas?"


def test_redactar_sin_intencion_no_llama_al_llm(monkeypatch):
    def _fallar_si_se_llama(pregunta, resultados):
        raise AssertionError("redactar no deberia llamar al LLM sin intencion")

    monkeypatch.setattr("core.graph._generar_respuesta", _fallar_si_se_llama)

    estado = _estado("pregunta de prueba")

    resultado = redactar(estado)

    assert resultado["respuesta"]


def _estado(pregunta: str) -> dict:
    return {
        "pregunta": pregunta,
        "intencion": None,
        "parametros": None,
        "resultados_herramientas": [],
        "accion_propuesta": None,
        "aprobacion": None,
        "respuesta": None,
    }


def _entender_y_ejecutar(pregunta: str) -> dict:
    """pregunta -> entender (Gemini real) -> ejecutar_herramientas, encadenados."""
    estado = _estado(pregunta)
    estado.update(entender(estado))
    estado.update(ejecutar_herramientas(estado))
    return estado


@pytest.mark.api
def test_stock_actual_via_grafo_filtra_los_insumos_bajo_minimo():
    estado = _entender_y_ejecutar("¿Qué insumos están por debajo del mínimo?")

    assert estado["intencion"].herramientas == ["stock_actual"]
    assert estado["intencion"].ambigua is False

    (entrada,) = _por_herramienta(estado["resultados_herramientas"], "stock_actual")
    assert isinstance(entrada.resultado, ListaStock)
    # valor conocido de evals/valores_base.md: 3 insumos bajo minimo
    nombres_bajo_minimo = {
        item.nombre for item in entrada.resultado.items if item.bajo_minimo
    }
    assert nombres_bajo_minimo == {"espinaca", "fresa", "palta"}


@pytest.mark.api
def test_consumo_promedio_via_grafo_normaliza_insumo_con_tilde():
    estado = _entender_y_ejecutar("¿Cuál es el consumo promedio diario de plátano?")

    assert estado["intencion"].herramientas == ["consumo_promedio"]
    assert estado["parametros"].insumo == "platano"

    (entrada,) = _por_herramienta(estado["resultados_herramientas"], "consumo_promedio")
    assert isinstance(entrada.resultado, ConsumoInsumo)
    assert entrada.resultado.insumo == "platano"


@pytest.mark.api
def test_ventas_por_periodo_via_grafo_usa_el_rango_de_julio():
    estado = _entender_y_ejecutar(
        "¿Cómo van las ventas de julio 2026 agrupadas por producto?"
    )

    assert estado["intencion"].herramientas == ["ventas_por_periodo"]

    (entrada,) = _por_herramienta(
        estado["resultados_herramientas"], "ventas_por_periodo"
    )
    assert isinstance(entrada.resultado, ResumenVentas)
    # valor conocido de evals/valores_base.md: ingreso total de julio 2026
    assert entrada.resultado.total_ingresos == pytest.approx(5481.00, abs=0.01)


@pytest.mark.api
def test_margen_por_producto_via_grafo_usa_el_mes_correcto():
    estado = _entender_y_ejecutar("¿Cuál producto tuvo mejor margen en julio 2026?")

    assert estado["intencion"].herramientas == ["margen_por_producto"]
    assert estado["parametros"].mes == "2026-07"

    (entrada,) = _por_herramienta(
        estado["resultados_herramientas"], "margen_por_producto"
    )
    assert isinstance(entrada.resultado, ListaMargenes)


@pytest.mark.api
def test_clientes_inactivos_via_grafo():
    estado = _entender_y_ejecutar("¿Qué clientes frecuentes dejaron de venir?")

    assert estado["intencion"].herramientas == ["clientes_inactivos"]

    (entrada,) = _por_herramienta(
        estado["resultados_herramientas"], "clientes_inactivos"
    )
    assert isinstance(entrada.resultado, ListaClientes)


@pytest.mark.api
def test_sugerir_compra_via_grafo_para_que_compro_esta_semana():
    estado = _entender_y_ejecutar("¿Qué debería comprar esta semana?")

    assert estado["intencion"].herramientas == ["sugerir_compra"]

    (entrada,) = _por_herramienta(estado["resultados_herramientas"], "sugerir_compra")
    assert isinstance(entrada.resultado, ListaSugerencias)


@pytest.mark.api
def test_redactar_via_grafo_distingue_urgencia_en_que_compro_esta_semana():
    """Con la semilla actual, fresa sale urgente y el resto (espinaca,
    palta) esta_semana (verificado a mano contra sugerir_compra). La
    respuesta final debe conservar esa distincion, no mezclar todo bajo
    una sola etiqueta.
    """
    estado = _entender_y_ejecutar("¿Qué debería comprar esta semana?")
    estado.update(redactar(estado))
    respuesta = estado["respuesta"].lower()

    (entrada,) = _por_herramienta(estado["resultados_herramientas"], "sugerir_compra")
    urgencias = {
        item.insumo: item.urgencia
        for proveedor in entrada.resultado.proveedores
        for item in proveedor.items
    }
    # dato conocido contra la semilla actual, ver evals/valores_base.md
    assert urgencias.get("fresa") == "urgente"
    assert urgencias.get("espinaca") == "esta_semana"
    assert urgencias.get("palta") == "esta_semana"

    posiciones_urgente = [m.start() for m in re.finditer("urgen", respuesta)]
    assert posiciones_urgente, f"la respuesta no distingue urgencia: {respuesta!r}"

    def _distancia_a_urgente(insumo: str) -> int:
        posicion = respuesta.find(insumo)
        assert posicion >= 0, f"la respuesta no menciona {insumo}: {respuesta!r}"
        return min(abs(posicion - p) for p in posiciones_urgente)

    distancia_fresa = _distancia_a_urgente("fresa")
    for insumo in ("espinaca", "palta"):
        assert distancia_fresa < _distancia_a_urgente(insumo), (
            f"fresa (urgente) deberia quedar mas cerca de 'urgente' que "
            f"{insumo} (esta_semana): {respuesta!r}"
        )


@pytest.mark.api
def test_comparar_ventas_via_grafo_de_dos_periodos():
    estado = _entender_y_ejecutar(
        "¿Cómo vendí en julio 2026 comparado con junio 2026?"
    )

    assert estado["intencion"].herramientas == ["ventas_por_periodo"]
    assert estado["parametros"].desde.isoformat().startswith("2026-07")
    assert estado["parametros"].desde_comparacion.isoformat().startswith("2026-06")

    entradas = _por_herramienta(estado["resultados_herramientas"], "ventas_por_periodo")
    assert len(entradas) == 2
    for entrada in entradas:
        assert isinstance(entrada.resultado, ResumenVentas), (
            f"parametros={entrada.parametros} devolvio "
            f"{type(entrada.resultado).__name__}: {entrada.resultado}"
        )


@pytest.mark.api
def test_margen_y_clientes_inactivos_via_grafo_en_una_pregunta():
    estado = _entender_y_ejecutar(
        "¿Cuál fue el margen de julio 2026 y qué clientes frecuentes dejaron "
        "de venir?"
    )

    assert set(estado["intencion"].herramientas) == {
        "margen_por_producto",
        "clientes_inactivos",
    }
    assert estado["parametros"].mes == "2026-07"

    (margenes,) = _por_herramienta(
        estado["resultados_herramientas"], "margen_por_producto"
    )
    (clientes,) = _por_herramienta(
        estado["resultados_herramientas"], "clientes_inactivos"
    )
    assert isinstance(margenes.resultado, ListaMargenes)
    assert isinstance(clientes.resultado, ListaClientes)


_PATRON_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _numeros_en_texto(texto: str) -> list[float]:
    """Todo numero que aparece en un texto libre, tolerando coma o punto
    como separador decimal (la respuesta esta en español)."""
    return [float(token.replace(",", ".")) for token in _PATRON_NUMERO.findall(texto)]


def _numeros_en(obj) -> set[float]:
    """Todo numero presente en una estructura anidada (dict/list/escalar),
    mas el largo de cada lista: contar cuantos items hay no es inventar un
    dato, es describir lo que ya vino, asi que tambien cuenta como valido.
    """
    numeros: set[float] = set()
    if isinstance(obj, dict):
        for valor in obj.values():
            numeros |= _numeros_en(valor)
    elif isinstance(obj, list):
        numeros.add(float(len(obj)))
        for item in obj:
            numeros |= _numeros_en(item)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        numeros.add(float(obj))
    return numeros


@pytest.mark.api
def test_redactar_no_inventa_numeros_fuera_del_resultado():
    resultado = ListaStock(
        items=[
            ItemStock(
                nombre="cafe",
                unidad="kg",
                stock=12.5,
                minimo=5.0,
                bajo_minimo=False,
                proveedor="Proveedor X",
            ),
            ItemStock(
                nombre="leche",
                unidad="litro",
                stock=3.0,
                minimo=4.0,
                bajo_minimo=True,
                proveedor="Proveedor Y",
            ),
        ]
    )
    estado = _estado("¿Cuánto stock de café y de leche tenemos?")
    estado["intencion"] = Intencion(herramientas=["stock_actual"], ambigua=False)
    estado["resultados_herramientas"] = [
        ResultadoHerramienta(herramienta="stock_actual", parametros={}, resultado=resultado)
    ]

    salida = redactar(estado)
    respuesta = salida["respuesta"]

    numeros_validos = _numeros_en(resultado.model_dump())
    for numero in _numeros_en_texto(respuesta):
        assert numero in numeros_validos, (
            f"la respuesta menciona {numero}, que no aparece en el resultado "
            f"({numeros_validos}): {respuesta!r}"
        )
