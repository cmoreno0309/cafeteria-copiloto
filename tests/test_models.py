"""Pruebas de core/models.py: cada modelo valida un ejemplo correcto
y rechaza uno con un tipo invalido.
"""

import pytest
from pydantic import ValidationError

from core.models import (
    ClienteInactivo,
    ConsumoInsumo,
    FilaVenta,
    ItemOrden,
    ItemStock,
    ListaClientes,
    ListaMargenes,
    ListaStock,
    MargenProducto,
    OrdenCompra,
    ResumenVentas,
)


def test_item_stock_valido():
    item = ItemStock(
        nombre="platano",
        unidad="kg",
        stock=5.0,
        minimo=2.0,
        bajo_minimo=False,
        proveedor="Frutas del Valle",
    )
    assert item.stock == 5.0


def test_item_stock_invalido():
    with pytest.raises(ValidationError):
        ItemStock(
            nombre="platano",
            unidad="kg",
            stock="mucho",
            minimo=2.0,
            bajo_minimo=False,
            proveedor="Frutas del Valle",
        )


def test_lista_stock_valida():
    lista = ListaStock(
        items=[
            ItemStock(
                nombre="platano",
                unidad="kg",
                stock=5.0,
                minimo=2.0,
                bajo_minimo=False,
                proveedor="Frutas del Valle",
            )
        ]
    )
    assert len(lista.items) == 1


def test_lista_stock_invalida():
    with pytest.raises(ValidationError):
        ListaStock(items="no es una lista")


def test_consumo_insumo_valido():
    consumo = ConsumoInsumo(
        insumo="platano",
        dias_analizados=14,
        consumo_diario=1.2,
        dias_de_cobertura=4.5,
    )
    assert consumo.dias_de_cobertura == 4.5


def test_consumo_insumo_permite_cobertura_none():
    consumo = ConsumoInsumo(
        insumo="platano",
        dias_analizados=14,
        consumo_diario=0.0,
        dias_de_cobertura=None,
    )
    assert consumo.dias_de_cobertura is None


def test_consumo_insumo_invalido():
    with pytest.raises(ValidationError):
        ConsumoInsumo(
            insumo="platano",
            dias_analizados="catorce",
            consumo_diario=1.2,
            dias_de_cobertura=4.5,
        )


def test_fila_venta_valida():
    fila = FilaVenta(etiqueta="2026-07", ingresos=1200.5, unidades=80)
    assert fila.unidades == 80


def test_fila_venta_invalida():
    with pytest.raises(ValidationError):
        FilaVenta(etiqueta="2026-07", ingresos="mucho", unidades=80)


def test_resumen_ventas_valido():
    resumen = ResumenVentas(
        total_ingresos=5481.0,
        total_unidades=320,
        filas=[FilaVenta(etiqueta="2026-07", ingresos=5481.0, unidades=320)],
    )
    assert resumen.total_unidades == 320


def test_resumen_ventas_invalido():
    with pytest.raises(ValidationError):
        ResumenVentas(
            total_ingresos=5481.0,
            total_unidades="trescientos",
            filas=[],
        )


def test_margen_producto_valido():
    margen = MargenProducto(
        producto="Batido verde",
        precio=4.5,
        costo=1.8,
        margen_unitario=2.7,
        margen_pct=60.0,
        unidades_vendidas=50,
        margen_total=135.0,
    )
    assert margen.margen_pct == 60.0


def test_margen_producto_invalido():
    with pytest.raises(ValidationError):
        MargenProducto(
            producto="Batido verde",
            precio=4.5,
            costo=1.8,
            margen_unitario=2.7,
            margen_pct=60.0,
            unidades_vendidas="cincuenta",
            margen_total=135.0,
        )


def test_lista_margenes_valida():
    lista = ListaMargenes(
        items=[
            MargenProducto(
                producto="Batido verde",
                precio=4.5,
                costo=1.8,
                margen_unitario=2.7,
                margen_pct=60.0,
                unidades_vendidas=50,
                margen_total=135.0,
            )
        ]
    )
    assert len(lista.items) == 1


def test_lista_margenes_invalida():
    with pytest.raises(ValidationError):
        ListaMargenes(items="no es una lista")


def test_cliente_inactivo_valido():
    cliente = ClienteInactivo(
        nombre="Ana Torres",
        ultima_compra="2026-06-10",
        dias_sin_venir=32,
        compras_totales=8,
        ticket_promedio=6.25,
    )
    assert cliente.dias_sin_venir == 32


def test_cliente_inactivo_invalido():
    with pytest.raises(ValidationError):
        ClienteInactivo(
            nombre="Ana Torres",
            ultima_compra="fecha-invalida",
            dias_sin_venir=32,
            compras_totales=8,
            ticket_promedio=6.25,
        )


def test_lista_clientes_valida():
    lista = ListaClientes(
        items=[
            ClienteInactivo(
                nombre="Ana Torres",
                ultima_compra="2026-06-10",
                dias_sin_venir=32,
                compras_totales=8,
                ticket_promedio=6.25,
            )
        ]
    )
    assert len(lista.items) == 1


def test_lista_clientes_invalida():
    with pytest.raises(ValidationError):
        ListaClientes(items="no es una lista")


def test_item_orden_valido():
    item = ItemOrden(insumo="espinaca", cantidad=3.5, unidad="kg")
    assert item.cantidad == 3.5


def test_item_orden_invalido():
    with pytest.raises(ValidationError):
        ItemOrden(insumo="espinaca", cantidad="tres", unidad="kg")


def test_orden_compra_valida():
    orden = OrdenCompra(
        id=1,
        fecha="2026-08-11",
        proveedor="Frutas del Valle",
        estado="aprobada",
        aprobada_por="dueña",
        aprobada_en="2026-08-11T10:00:00",
        items=[ItemOrden(insumo="espinaca", cantidad=3.5, unidad="kg")],
    )
    assert orden.estado == "aprobada"


def test_orden_compra_permite_aprobacion_none():
    orden = OrdenCompra(
        id=1,
        fecha="2026-08-11",
        proveedor="Frutas del Valle",
        estado="propuesta",
        aprobada_por=None,
        aprobada_en=None,
        items=[ItemOrden(insumo="espinaca", cantidad=3.5, unidad="kg")],
    )
    assert orden.aprobada_por is None


def test_orden_compra_invalida():
    with pytest.raises(ValidationError):
        OrdenCompra(
            id="uno",
            fecha="2026-08-11",
            proveedor="Frutas del Valle",
            estado="aprobada",
            aprobada_por="dueña",
            aprobada_en="2026-08-11T10:00:00",
            items=[ItemOrden(insumo="espinaca", cantidad=3.5, unidad="kg")],
        )
