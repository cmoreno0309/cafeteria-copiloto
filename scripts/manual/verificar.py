"""Paso 2 del ciclo manual: confirma la pausa y que no se inserto nada.

Lee el estado del grafo desde el checkpointer (sin recalcular nada) y
consulta ordenes_compra directo por SQL, para comprobar que aplicar_accion
todavia no corrio.

Uso:
    py -m scripts.manual.verificar
    py -m scripts.manual.verificar --thread mi-hilo
"""

import argparse

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
    args = parser.parse_args()

    config = config_grafo(args.thread)
    grafo = construir_grafo()
    estado = grafo.get_state(config)

    if not estado.tasks or not estado.tasks[0].interrupts:
        print(f"No hay ninguna pausa pendiente en el thread '{args.thread}'.")
        print("¿Corriste antes 'py -m scripts.manual.pedir'?")
        return

    propuesta = estado.tasks[0].interrupts[0].value
    print(f"Pausa confirmada: propuesta de '{propuesta['proveedor']}' esperando aprobacion.")

    conexion = get_conn()
    try:
        total = conexion.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()[0]
        ordenes = conexion.execute(
            "SELECT id, proveedor, estado FROM ordenes_compra"
        ).fetchall()
    finally:
        conexion.close()

    print(f"ordenes_compra tiene {total} fila(s) ahora mismo:")
    for orden_id, proveedor, estado_orden in ordenes:
        print(f"  - #{orden_id} {proveedor} ({estado_orden})")

    print()
    print("Si ese numero es igual al de antes de correr pedir.py, nada se")
    print("inserto todavia. Siguiente:")
    print(f"  py -m scripts.manual.aprobar --thread {args.thread}")


if __name__ == "__main__":
    main()
