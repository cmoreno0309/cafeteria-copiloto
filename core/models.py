"""Modelos Pydantic de entrada y salida de las herramientas de core/tools.

Ningun modelo contiene logica de negocio: solo forma y tipos, tal como
los describe SPEC.md seccion 3.
"""

from datetime import date, datetime

from pydantic import BaseModel


# 3.1 stock_actual


class ItemStock(BaseModel):
    nombre: str
    unidad: str
    stock: float
    minimo: float
    bajo_minimo: bool
    proveedor: str


class ListaStock(BaseModel):
    items: list[ItemStock]


# 3.2 consumo_promedio


class ConsumoInsumo(BaseModel):
    insumo: str
    dias_analizados: int
    consumo_diario: float
    dias_de_cobertura: float | None


# 3.3 ventas_por_periodo


class FilaVenta(BaseModel):
    etiqueta: str
    ingresos: float
    unidades: int


class ResumenVentas(BaseModel):
    total_ingresos: float
    total_unidades: int
    filas: list[FilaVenta]


# 3.4 margen_por_producto


class MargenProducto(BaseModel):
    producto: str
    precio: float
    costo: float
    margen_unitario: float
    margen_pct: float
    unidades_vendidas: int
    margen_total: float


class ListaMargenes(BaseModel):
    items: list[MargenProducto]


# 3.5 clientes_inactivos


class ClienteInactivo(BaseModel):
    nombre: str
    ultima_compra: date
    dias_sin_venir: int
    compras_totales: int
    ticket_promedio: float


class ListaClientes(BaseModel):
    items: list[ClienteInactivo]


# 3.6 crear_orden_compra


class ItemOrden(BaseModel):
    insumo: str
    cantidad: float
    unidad: str


class OrdenCompra(BaseModel):
    id: int
    fecha: date
    proveedor: str
    estado: str
    aprobada_por: str | None
    aprobada_en: datetime | None
    items: list[ItemOrden]
