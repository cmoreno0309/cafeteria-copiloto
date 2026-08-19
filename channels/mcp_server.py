"""Servidor MCP: expone las herramientas de lectura del copiloto.

Envoltorio delgado (regla 5 de CLAUDE.md): no contiene logica de negocio,
solo declara cada herramienta de core/tools/ con su descripcion y sus
parametros para que un cliente MCP (ej. Claude Desktop) sepa cuando
llamarla. Las mismas funciones se llaman directo desde el grafo
(core/graph.py).

Criterio de que se expone: si la herramienta escribe en la base, no su
nombre. Las 6 herramientas de core/tools/ que solo leen se exponen aca.
crear_orden_compra es la unica excluida: escribe una orden en la base, y
eso solo puede pasar despues del interrupt de aprobacion humana del grafo
(core/graph.py: proponer_accion / aplicar_accion), nunca directo desde un
cliente MCP.

Cada herramienta expone los mismos parametros "de la pregunta" que ya usa
el grafo (ver los `_kwargs_*` de core/graph.py), no la firma completa de
la funcion interna: los umbrales fijos (la ventana de consumo_promedio,
los dias/minimo_compras de clientes_inactivos) no son configurables desde
afuera, son parte de la regla de negocio.
"""

from datetime import date

from mcp.server.mcpserver import MCPServer

from core.tools.clientes_inactivos import clientes_inactivos as _clientes_inactivos
from core.tools.consumo_promedio import consumo_promedio as _consumo_promedio
from core.tools.margen_por_producto import margen_por_producto as _margen_por_producto
from core.tools.stock_actual import stock_actual as _stock_actual
from core.tools.sugerir_compra import sugerir_compra as _sugerir_compra
from core.tools.ventas_por_periodo import ventas_por_periodo as _ventas_por_periodo

servidor = MCPServer("cafeteria-copiloto")


@servidor.tool(
    name="stock_actual",
    description="Stock de cada insumo y si esta por debajo del minimo.",
)
def stock_actual(proveedor: str | None = None) -> dict:
    return _stock_actual(proveedor=proveedor).model_dump(mode="json")


@servidor.tool(
    name="consumo_promedio",
    description=(
        "Consumo diario promedio de un insumo, sobre una ventana fija de "
        "14 dias (no configurable desde la pregunta)."
    ),
)
def consumo_promedio(insumo: str) -> dict:
    return _consumo_promedio(insumo=insumo).model_dump(mode="json")


@servidor.tool(
    name="ventas_por_periodo",
    description=(
        "Ventas agrupadas por dia, semana, mes, producto o categoria, en "
        "el rango [desde, hasta]. Para comparar dos periodos (ej. 'julio "
        "contra junio'), llama esta herramienta dos veces, una por cada "
        "rango."
    ),
)
def ventas_por_periodo(desde: date, hasta: date, agrupar_por: str) -> dict:
    return _ventas_por_periodo(
        desde=desde, hasta=hasta, agrupar_por=agrupar_por
    ).model_dump(mode="json")


@servidor.tool(
    name="margen_por_producto",
    description="Margen de cada producto en un mes (formato YYYY-MM).",
)
def margen_por_producto(mes: str) -> dict:
    return _margen_por_producto(mes=mes).model_dump(mode="json")


@servidor.tool(
    name="clientes_inactivos",
    description=(
        "Clientes frecuentes que dejaron de comprar, con umbrales fijos "
        "(no configurables desde la pregunta). Por cada cliente devuelve "
        "tambien compras_totales y ticket_promedio: sirve para preguntas "
        "sobre un cliente puntual de esa lista (ej. '¿cuantas compras "
        "habia hecho [cliente] antes de dejar de venir?'), no solo para "
        "contar cuantos hay."
    ),
)
def clientes_inactivos() -> dict:
    return _clientes_inactivos().model_dump(mode="json")


@servidor.tool(
    name="sugerir_compra",
    description=(
        "Que insumos comprar esta semana, con cantidad y urgencia. Ya "
        "orquesta stock y consumo internamente: para 'que compro esta "
        "semana' no hace falta pedir stock_actual ni consumo_promedio "
        "por separado."
    ),
)
def sugerir_compra() -> dict:
    return _sugerir_compra().model_dump(mode="json")


if __name__ == "__main__":
    servidor.run()
