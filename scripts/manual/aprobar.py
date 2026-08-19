"""Paso 3 del ciclo manual: reanuda el grafo con la decision de aprobacion.

Manda un Command(resume=...) al mismo thread_id que uso pedir.py. Con
--rechazar prueba el camino de rechazo en vez del de aprobacion, para
confirmar que tampoco inserta nada en ese caso.

Uso:
    py -m scripts.manual.aprobar
    py -m scripts.manual.aprobar --thread mi-hilo
    py -m scripts.manual.aprobar --aprobada-por "socia"
    py -m scripts.manual.aprobar --rechazar
"""

import argparse

from langgraph.types import Command

from core.db import get_conn
from core.graph import construir_grafo
from scripts.manual._comun import THREAD_POR_DEFECTO, config_grafo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--thread",
        default=THREAD_POR_DEFECTO,
        help=f"thread_id del checkpointer (default: {THREAD_POR_DEFECTO})",
    )
    parser.add_argument(
        "--aprobada-por",
        default="dueña (prueba manual)",
        help="quien aprueba la orden (ignorado con --rechazar)",
    )
    parser.add_argument(
        "--rechazar",
        action="store_true",
        help="reanuda con aprobada=False en vez de aprobarla",
    )
    args = parser.parse_args()

    config = config_grafo(args.thread)
    grafo = construir_grafo()

    resume = (
        {"aprobada": False}
        if args.rechazar
        else {"aprobada": True, "aprobada_por": args.aprobada_por}
    )
    resultado = grafo.invoke(Command(resume=resume), config=config)

    print(f"Respuesta del grafo (thread={args.thread}):")
    print(f"  {resultado.get('respuesta')}")

    conexion = get_conn()
    try:
        ordenes = conexion.execute(
            "SELECT id, proveedor, estado, aprobada_por FROM ordenes_compra"
        ).fetchall()
    finally:
        conexion.close()

    print()
    print(f"ordenes_compra tiene {len(ordenes)} fila(s) ahora:")
    for orden_id, proveedor, estado_orden, aprobada_por in ordenes:
        print(f"  - #{orden_id} {proveedor} ({estado_orden}, aprobada_por={aprobada_por})")


if __name__ == "__main__":
    main()
