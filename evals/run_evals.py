"""Corre evals/dataset.yaml contra el grafo y escribe evals/resultados.md.

Mide dos cosas por separado, por caso (SPEC.md §5):
- acierto de herramienta: ¿llamó exactamente las herramientas esperadas?
- acierto de valor: ¿el número (o texto, para los casos ambiguos) de la
  respuesta final coincide con el esperado?

El valor esperado de cada caso NO lo calcula este script ni el agente: viene
calculado a mano en evals/dataset.yaml (ver evals/propuesta_dataset_1.15.md
para el detalle de cómo se llegó a cada número).

Corre contra una COPIA TEMPORAL de data/cafeteria.db, nunca contra la base
real: uno de los 15 casos (A2) es un pedido de ejecutar una compra, y si el
grafo fallara podría insertar una orden de verdad. La copia se descarta al
terminar.
"""

import argparse
import re
import shutil
import sqlite3
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

import core.db as db
from core.graph import EstadoGrafo, ErrorHerramienta, _checkpointer, construir_grafo

RUTA_DATASET = Path("evals/dataset.yaml")
RUTA_RESULTADOS = Path("evals/resultados.md")
RUTA_DB_REAL = Path("data/cafeteria.db")

FECHA_REFERENCIA_DEFAULT = date(2026, 8, 16)
"""La fecha con la que evals/dataset.yaml calculó a mano el valor esperado
de los 5 casos que anclan a `hoy` (S3, S4, C1, C2, A2). Correr con una fecha
distinta es válido (ver --fecha-referencia) pero esos 5 casos van a fallar
si la base no cambió, porque su ventana de 14/21 días ya no cae donde se
calculó — no es un error del grafo.
"""

UMBRAL_CASOS = 13
PATRON_NUMERO = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class ResultadoCaso:
    id: str
    caso: str
    categoria: str
    pregunta: str
    herramientas_esperadas: list[str]
    herramientas_llamadas: list[str]
    acierto_herramienta: bool
    acierto_valor: bool
    respuesta: str
    detalle: str = ""


def _sin_tildes(texto: str) -> str:
    """Quita diacriticos y pasa a minusculas, para comparar sin tildes."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def _campo(entrada, nombre: str):
    """Lee un campo de una entrada de resultados_herramientas / intencion,
    ya sea que el checkpointer la haya devuelto como modelo Pydantic o,
    tras un roundtrip de serializacion, como dict plano.
    """
    return entrada[nombre] if isinstance(entrada, dict) else getattr(entrada, nombre)


def _llamadas_normalizadas(salida: dict) -> list[tuple[str, bool]]:
    """(nombre_herramienta, tuvo_resultado_real) por cada entrada de
    resultados_herramientas, en el orden en que se llamaron.
    tuvo_resultado_real=False marca un ErrorHerramienta: la llamada se hizo
    pero no produjo un dato usable para responder.
    """
    normalizadas = []
    for entrada in salida.get("resultados_herramientas", []):
        nombre = _campo(entrada, "herramienta")
        resultado = _campo(entrada, "resultado")
        es_error = isinstance(resultado, ErrorHerramienta) or (
            isinstance(resultado, dict) and set(resultado) == {"mensaje"}
        )
        normalizadas.append((nombre, not es_error))
    return normalizadas


def _numeros_en_texto(texto: str) -> list[float]:
    """Extrae los numeros literales de un texto.

    redactar() tiene instruccion estricta de copiar los numeros tal cual
    vienen del JSON de las herramientas (que Pydantic siempre serializa con
    punto decimal, sin separador de miles), asi que no hace falta tolerar
    formatos con coma decimal o miles: alcanza con un regex simple.
    """
    return [float(coincidencia) for coincidencia in PATRON_NUMERO.findall(texto)]


def _contar_ordenes(ruta_db: Path) -> int:
    conexion = sqlite3.connect(ruta_db)
    try:
        (total,) = conexion.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()
        return total
    finally:
        conexion.close()


def _cargar_dataset() -> list[dict]:
    with RUTA_DATASET.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def _evaluar_herramienta(caso: dict, llamadas: list[tuple[str, bool]]) -> bool:
    """Compara los nombres llamados contra herramientas_esperadas.

    Solo A1 trae herramientas_alternativas: la otra forma valida de mostrar
    su ambiguedad (ver notas del caso en evals/dataset.yaml) es que Gemini
    no marque ambigua=True y en cambio la herramienta se llame y falle por
    falta de un parametro obligatorio (ej. el periodo) — por eso esa rama
    solo cuenta si NINGUNA llamada produjo un resultado real: si el nombre
    coincide pero la llamada tuvo exito, no es la misma ambiguedad, es un
    acierto de ruteo distinto (y probablemente un fallo real).
    """
    nombres = sorted({nombre for nombre, _ in llamadas})
    todas_exitosas = all(exito for _, exito in llamadas)

    esperadas = sorted(set(caso.get("herramientas_esperadas", [])))
    if nombres == esperadas and todas_exitosas:
        return True

    for alternativa in caso.get("herramientas_alternativas", []):
        if nombres == sorted(set(alternativa)) and not todas_exitosas:
            return True
    return False


def _evaluar_valor(
    caso: dict, salida: dict, escritura_inesperada: bool
) -> tuple[bool, str]:
    """Decide el acierto de valor segun `tipo`. Ver el encabezado de
    evals/dataset.yaml para la definicion de cada tipo.
    """
    if escritura_inesperada:
        return False, (
            "se creo o modifico una orden de compra sin aprobacion; ninguno "
            "de estos 15 casos deberia escribir en la base"
        )

    respuesta = salida.get("respuesta") or ""
    tipo = caso["tipo"]

    if tipo == "ambigua":
        # Ni A1 (ambigua ya en entender) ni A2 (ambigua recien en
        # proponer_accion, por el proveedor) deberian llegar a armar una
        # propuesta concreta: eso es lo que valida accion_propuesta,
        # ausente en ambos caminos correctos. No se busca un "?" literal
        # en el texto: el motivo de entender es una explicacion, no
        # necesariamente esta frased como pregunta.
        if salida.get("accion_propuesta") is not None:
            return False, "armó una propuesta de compra concreta en vez de pedir aclaración"
        if not respuesta.strip():
            return False, "la respuesta llegó vacía"
        return True, ""

    numeros = _numeros_en_texto(respuesta)
    tolerancia = float(caso.get("tolerancia", 0.0))

    if tipo == "conteo":
        objetivo = float(caso["valor_esperado"])
        if any(n == objetivo for n in numeros):
            return True, ""
        return False, f"no aparece {caso['valor_esperado']} en la respuesta"

    if tipo == "monto":
        objetivo = float(caso["valor_esperado"])
        if any(abs(n - objetivo) <= tolerancia for n in numeros):
            return True, ""
        return False, (
            f"no aparece un numero cercano a {caso['valor_esperado']} "
            f"(tolerancia {tolerancia})"
        )

    if tipo == "monto_par":
        objetivo_a = float(caso["valor_esperado"])
        objetivo_b = float(caso["valor_esperado_comparacion"])
        tiene_a = any(abs(n - objetivo_a) <= tolerancia for n in numeros)
        tiene_b = any(abs(n - objetivo_b) <= tolerancia for n in numeros)
        if tiene_a and tiene_b:
            return True, ""
        faltantes = [
            str(v) for v, ok in ((objetivo_a, tiene_a), (objetivo_b, tiene_b)) if not ok
        ]
        return False, f"faltan en la respuesta: {', '.join(faltantes)}"

    if tipo == "texto_monto":
        objetivo_texto = _sin_tildes(caso["valor_esperado_texto"])
        tiene_texto = objetivo_texto in _sin_tildes(respuesta)
        objetivo_monto = float(caso["valor_esperado"])
        tiene_monto = any(abs(n - objetivo_monto) <= tolerancia for n in numeros)
        if tiene_texto and tiene_monto:
            return True, ""
        problemas = []
        if not tiene_texto:
            problemas.append(f"falta '{caso['valor_esperado_texto']}'")
        if not tiene_monto:
            problemas.append(f"falta un numero cercano a {objetivo_monto}")
        return False, "; ".join(problemas)

    raise ValueError(f"tipo de caso desconocido en el dataset: {tipo}")


def _correr_caso(grafo, caso: dict, fecha_referencia: date, ruta_db_temporal: Path) -> ResultadoCaso:
    thread_id = f"eval-{fecha_referencia.isoformat()}-{caso['id']}"
    config = {"configurable": {"thread_id": thread_id}}
    estado_inicial: EstadoGrafo = {"pregunta": caso["pregunta"], "hoy": fecha_referencia}

    ordenes_antes = _contar_ordenes(ruta_db_temporal)
    salida = grafo.invoke(estado_inicial, config=config)
    ordenes_despues = _contar_ordenes(ruta_db_temporal)

    esperadas = sorted(set(caso.get("herramientas_esperadas", [])))

    if "__interrupt__" in salida:
        # Nunca se aprueba automaticamente en un eval: si algo pauso aca es
        # porque, con esta fecha_referencia, dejo de ser ambiguo (o el
        # grafo esta enrutando distinto a lo esperado). Cualquiera de las
        # dos es una falla del caso, no algo para resolver solo.
        return ResultadoCaso(
            id=caso["id"],
            caso=caso["caso"],
            categoria=caso["categoria"],
            pregunta=caso["pregunta"],
            herramientas_esperadas=esperadas,
            herramientas_llamadas=[],
            acierto_herramienta=False,
            acierto_valor=False,
            respuesta="",
            detalle=(
                "el grafo quedo pausado esperando aprobacion (interrupt) en "
                "vez de responder"
            ),
        )

    llamadas = _llamadas_normalizadas(salida)
    herramientas_llamadas = sorted({nombre for nombre, _ in llamadas})
    acierto_herramienta = _evaluar_herramienta(caso, llamadas)

    respuesta = salida.get("respuesta") or ""
    escritura_inesperada = ordenes_despues != ordenes_antes
    acierto_valor, detalle = _evaluar_valor(caso, salida, escritura_inesperada)

    return ResultadoCaso(
        id=caso["id"],
        caso=caso["caso"],
        categoria=caso["categoria"],
        pregunta=caso["pregunta"],
        herramientas_esperadas=esperadas,
        herramientas_llamadas=herramientas_llamadas,
        acierto_herramienta=acierto_herramienta,
        acierto_valor=acierto_valor,
        respuesta=respuesta,
        detalle=detalle,
    )


def _escapar_celda(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def _escribir_resultados(resultados: list[ResultadoCaso], fecha_referencia: date) -> None:
    total = len(resultados)
    aciertos_herramienta = sum(r.acierto_herramienta for r in resultados)
    aciertos_valor = sum(r.acierto_valor for r in resultados)

    lineas = [
        "# Resultados de evaluación",
        "",
        "Corrida contra una copia temporal de `data/cafeteria.db` "
        "(la base real no se toca). Fecha de referencia (`hoy`) usada para "
        f"anclar consumo_promedio, clientes_inactivos y sugerir_compra: "
        f"`{fecha_referencia.isoformat()}`.",
        "",
        f"- Acierto de herramienta: **{aciertos_herramienta}/{total}** "
        f"(umbral de cierre: {UMBRAL_CASOS}/{total})",
        f"- Acierto de valor: **{aciertos_valor}/{total}** "
        f"(umbral de cierre: {UMBRAL_CASOS}/{total})",
        "",
        "| id | caso | categoría | pregunta | herramienta | valor | detalle |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        lineas.append(
            "| {id} | {caso} | {categoria} | {pregunta} | {th} | {tv} | {detalle} |".format(
                id=r.id,
                caso=r.caso,
                categoria=r.categoria,
                pregunta=_escapar_celda(r.pregunta),
                th="OK" if r.acierto_herramienta else "FALLA",
                tv="OK" if r.acierto_valor else "FALLA",
                detalle=_escapar_celda(r.detalle),
            )
        )

    fallos = [r for r in resultados if not (r.acierto_herramienta and r.acierto_valor)]
    if fallos:
        lineas += ["", "## Detalle de los casos que fallaron", ""]
        for r in fallos:
            lineas.append(f"### {r.id} ({r.caso}) — {r.pregunta}")
            lineas.append("")
            lineas.append(
                f"- herramienta: {'OK' if r.acierto_herramienta else 'FALLA'} "
                f"— esperada `{r.herramientas_esperadas}`, llamada `{r.herramientas_llamadas}`"
            )
            lineas.append(f"- valor: {'OK' if r.acierto_valor else 'FALLA'} — {r.detalle}")
            lineas.append(f"- respuesta del agente: {r.respuesta or '(vacía)'}")
            lineas.append("")

    RUTA_RESULTADOS.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _imprimir_resumen(resultados: list[ResultadoCaso]) -> None:
    total = len(resultados)
    aciertos_herramienta = sum(r.acierto_herramienta for r in resultados)
    aciertos_valor = sum(r.acierto_valor for r in resultados)
    print(f"Acierto de herramienta: {aciertos_herramienta}/{total}")
    print(f"Acierto de valor: {aciertos_valor}/{total}")
    for r in resultados:
        if not (r.acierto_herramienta and r.acierto_valor):
            print(f"  {r.id} ({r.caso}): {r.detalle or 'ver herramientas esperadas/llamadas'}")
            print(f"    respuesta: {r.respuesta or '(vacía)'}")
    print(f"Detalle completo en {RUTA_RESULTADOS}")


def _parsear_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fecha-referencia",
        type=date.fromisoformat,
        default=FECHA_REFERENCIA_DEFAULT,
        help=(
            "Fecha 'hoy' para anclar las herramientas que no reciben un "
            "rango explicito (consumo_promedio, clientes_inactivos, "
            f"sugerir_compra). Default: {FECHA_REFERENCIA_DEFAULT.isoformat()}, "
            "la fecha con la que evals/dataset.yaml calculo a mano los 5 "
            "casos marcados."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parsear_args()
    casos = _cargar_dataset()

    with tempfile.TemporaryDirectory(prefix="cafeteria_evals_") as directorio:
        ruta_db_temporal = Path(directorio) / "cafeteria.db"
        shutil.copyfile(RUTA_DB_REAL, ruta_db_temporal)
        ruta_checkpoints_temporal = Path(directorio) / "checkpoints.db"

        ruta_db_original = db.DB_PATH
        db.DB_PATH = ruta_db_temporal
        checkpointer = _checkpointer(ruta_checkpoints_temporal)
        try:
            grafo = construir_grafo(checkpointer=checkpointer)
            resultados = [
                _correr_caso(grafo, caso, args.fecha_referencia, ruta_db_temporal)
                for caso in casos
            ]
        finally:
            db.DB_PATH = ruta_db_original
            # Cierra la conexion sqlite del checkpointer explicitamente:
            # en Windows, TemporaryDirectory.cleanup() no puede borrar un
            # archivo con un handle todavia abierto y revienta con
            # PermissionError al salir del with.
            checkpointer.conn.close()

    _escribir_resultados(resultados, args.fecha_referencia)
    _imprimir_resumen(resultados)


if __name__ == "__main__":
    main()
