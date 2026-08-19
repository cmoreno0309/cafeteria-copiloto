"""Paso 1 del ciclo manual: manda la orden al grafo y lo deja en pausa.

Usa el checkpointer y la base reales (data/checkpoints.db, data/cafeteria.db),
igual que un canal de verdad. El thread_id identifica esta conversacion para
que verificar.py y aprobar.py retomen el mismo hilo.

Uso:
    py -m scripts.manual.pedir
    py -m scripts.manual.pedir "arma la orden de compra de frutas"
    py -m scripts.manual.pedir "arma la orden de compra de frutas" --thread mi-hilo
"""

import argparse

from core.graph import construir_grafo
from scripts.manual._comun import THREAD_POR_DEFECTO, config_grafo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pregunta",
        nargs="?",
        default="arma la orden de compra de frutas",
        help="pedido a mandarle al grafo (default: orden de compra de frutas)",
    )
    parser.add_argument(
        "--thread",
        default=THREAD_POR_DEFECTO,
        help=f"thread_id del checkpointer (default: {THREAD_POR_DEFECTO})",
    )
    args = parser.parse_args()

    config = config_grafo(args.thread)
    grafo = construir_grafo()
    resultado = grafo.invoke({"pregunta": args.pregunta}, config=config)

    if "__interrupt__" in resultado:
        propuesta = resultado["__interrupt__"][0].value
        print(f"Pregunta: {args.pregunta}")
        print(f"Propuesta en pausa (thread={args.thread}):")
        print(f"  proveedor: {propuesta['proveedor']}")
        for item in propuesta["items"]:
            print(
                f"  - {item['insumo']}: {item['cantidad']} {item['unidad']} "
                f"(urgencia={item['urgencia']}, "
                f"costo_unitario_estimado={item['costo_unitario_estimado']})"
            )
        print(f"  total_estimado: {propuesta['total_estimado']}")
        print()
        print("Nada se inserto todavia. Siguiente:")
        print(f"  py -m scripts.manual.verificar --thread {args.thread}")
    else:
        print(f"El grafo no quedo en pausa (thread={args.thread}). Respuesta:")
        print(f"  {resultado.get('respuesta')}")
        print()
        print(
            "Esto pasa si la pregunta no se clasifico como accion=True, o si "
            "proponer_accion no pudo armar una propuesta sin ambiguedad "
            "(revisa la respuesta de arriba)."
        )


if __name__ == "__main__":
    main()
