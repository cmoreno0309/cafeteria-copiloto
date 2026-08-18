"""Reporta costo total y promedio por consulta de una corrida de evals ya
trazada en Langfuse (tarea 1.19).

Uso:
    py -m evals.costo_langfuse <session_id>

El session_id es el que imprime `evals/run_evals.py` al final de la
corrida cuando las trazas de Langfuse estan activas (LANGFUSE_PUBLIC_KEY y
LANGFUSE_SECRET_KEY definidas en .env).
"""

import argparse
import time

from langfuse import Langfuse

from core.config import get_langfuse_host, get_langfuse_public_key, get_langfuse_secret_key

ESPERA_MAXIMA_SEGUNDOS = 30
INTERVALO_SONDEO_SEGUNDOS = 2


def _cliente() -> Langfuse:
    public_key = get_langfuse_public_key()
    secret_key = get_langfuse_secret_key()
    if not public_key or not secret_key:
        raise RuntimeError(
            "Faltan LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY en .env: sin "
            "eso no hay con que autenticar la consulta a la API de Langfuse."
        )
    return Langfuse(public_key=public_key, secret_key=secret_key, host=get_langfuse_host())


def _esperar_trazas(cliente: Langfuse, session_id: str, esperadas: int) -> list:
    """Langfuse ingiere y calcula el costo de cada traza de forma
    asincrona: sondea hasta que aparezcan `esperadas` trazas con el costo
    ya calculado, o hasta ESPERA_MAXIMA_SEGUNDOS.
    """
    limite = time.monotonic() + ESPERA_MAXIMA_SEGUNDOS
    trazas: list = []
    while time.monotonic() < limite:
        trazas = cliente.api.trace.list(session_id=session_id, limit=100).data
        if len(trazas) >= esperadas and all(t.total_cost is not None for t in trazas):
            break
        time.sleep(INTERVALO_SONDEO_SEGUNDOS)
    return trazas


def _agregar(trazas: list) -> tuple[float, float, float | None]:
    """(costo_total, costo_promedio, latencia_promedio) a partir de una
    lista de trazas con atributos total_cost/latency (ambos opcionales:
    Langfuse los deja en None mientras no terminaron de calcularse).
    """
    if not trazas:
        return 0.0, 0.0, None
    costos = [t.total_cost or 0.0 for t in trazas]
    latencias = [t.latency for t in trazas if t.latency is not None]
    costo_total = sum(costos)
    costo_promedio = costo_total / len(trazas)
    latencia_promedio = sum(latencias) / len(latencias) if latencias else None
    return costo_total, costo_promedio, latencia_promedio


def reportar(session_id: str, esperadas: int = 15) -> None:
    cliente = _cliente()
    trazas = _esperar_trazas(cliente, session_id, esperadas)

    if not trazas:
        print(f"No aparecieron trazas para session_id={session_id} en Langfuse todavia.")
        return

    costo_total, costo_promedio, latencia_promedio = _agregar(trazas)

    print(f"Trazas encontradas: {len(trazas)}/{esperadas}")
    print(f"Costo total: ${costo_total:.6f}")
    print(f"Costo promedio por consulta: ${costo_promedio:.6f}")
    if latencia_promedio is not None:
        print(f"Latencia promedio por consulta: {latencia_promedio:.2f}s")
    if len(trazas) < esperadas:
        print(
            "Aviso: no llegaron todas las trazas esperadas todavia "
            "(la ingestion de Langfuse es asincrona) — volve a correr en "
            "unos segundos."
        )


def _parsear_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", help="session_id impreso por evals/run_evals.py")
    parser.add_argument(
        "--esperadas",
        type=int,
        default=15,
        help="cantidad de trazas esperadas antes de dejar de sondear (default 15)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parsear_args()
    reportar(args.session_id, args.esperadas)


if __name__ == "__main__":
    main()
