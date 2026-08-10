"""Genera datos sinteticos para la base de la cafeteria.

Carga insumos, productos y recetas desde data/*.csv (son los datos fijos de
SPEC.md) y genera clientes y ventas de forma aleatoria pero reproducible
(semilla fija) con la estacionalidad descrita en SPEC.md Seccion 2:
viernes y sabado 40% mas de ventas que un lunes, un producto en declive
sostenido y cinco clientes que dejan de comprar hace mas de 30 dias.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from core.db import get_conn, init_db

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DATOS = RAIZ / "data"

SEMILLA = 42
DIAS_HISTORIA = 60
NUM_CLIENTES = 25
NUM_CLIENTES_INACTIVOS = 5
CORTE_INACTIVIDAD = 31  # offsets >= este valor cuentan como "hace mas de 30 dias"
PRODUCTO_EN_DECLIVE = "Bowl de avena y fruta"
PROB_SIN_CLIENTE = 0.15
BASE_VENTAS_DIA = 10

MULTIPLICADOR_DIA = {
    0: 1.0,  # lunes
    1: 1.0,  # martes
    2: 1.0,  # miercoles
    3: 1.0,  # jueves
    4: 1.4,  # viernes
    5: 1.4,  # sabado
    6: 0.7,  # domingo
}

NOMBRES_CLIENTES = [
    "Maria Gonzalez", "Jose Perez", "Ana Rodriguez", "Carlos Fernandez",
    "Lucia Martinez", "Diego Sanchez", "Valentina Ramirez", "Andres Torres",
    "Camila Flores", "Javier Diaz", "Sofia Morales", "Miguel Castro",
    "Isabella Ortiz", "Fernando Rojas", "Daniela Vargas", "Ricardo Silva",
    "Paula Guerrero", "Sebastian Rios", "Gabriela Mendoza", "Alejandro Nunez",
    "Valeria Campos", "Rodrigo Herrera", "Antonella Paredes", "Emilio Chavez",
    "Renata Salazar",
]


def limpiar_tablas(conn):
    """Vacia las tablas en orden seguro para las foreign keys."""
    for tabla in ("ventas", "ordenes_compra", "recetas", "productos", "clientes", "insumos"):
        conn.execute(f"DELETE FROM {tabla}")


def cargar_insumos(conn):
    with open(RUTA_DATOS / "insumos.csv", encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            conn.execute(
                "INSERT INTO insumos (nombre, unidad, stock_actual, stock_minimo, "
                "costo_unitario, proveedor) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    fila["nombre"],
                    fila["unidad"],
                    float(fila["stock_actual"]),
                    float(fila["stock_minimo"]),
                    float(fila["costo_unitario"]),
                    fila["proveedor"],
                ),
            )


def cargar_productos(conn):
    with open(RUTA_DATOS / "productos.csv", encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            conn.execute(
                "INSERT INTO productos (nombre, precio_venta, categoria) VALUES (?, ?, ?)",
                (fila["nombre"], float(fila["precio_venta"]), fila["categoria"]),
            )


def cargar_recetas(conn):
    productos_id = dict(conn.execute("SELECT nombre, id FROM productos"))
    insumos_id = dict(conn.execute("SELECT nombre, id FROM insumos"))
    with open(RUTA_DATOS / "recetas.csv", encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            conn.execute(
                "INSERT INTO recetas (producto_id, insumo_id, cantidad) VALUES (?, ?, ?)",
                (
                    productos_id[fila["producto"]],
                    insumos_id[fila["insumo"]],
                    float(fila["cantidad"]),
                ),
            )


def generar_clientes(conn, rng, hoy):
    ids = []
    for nombre in NOMBRES_CLIENTES:
        fecha_registro = hoy - timedelta(days=rng.randint(45, 500))
        cursor = conn.execute(
            "INSERT INTO clientes (nombre, fecha_registro) VALUES (?, ?)",
            (nombre, fecha_registro.isoformat()),
        )
        ids.append(cursor.lastrowid)
    return ids


def _peso_producto(nombre, offset):
    """Pesa la probabilidad de venta de cada producto para un dia dado.

    El producto en declive vende mucho hace 60 dias y poco hoy (offset=0);
    el resto de productos mantiene un peso parejo.
    """
    if nombre != PRODUCTO_EN_DECLIVE:
        return 1.0
    proporcion = offset / (DIAS_HISTORIA - 1)
    return 0.3 + (2.5 - 0.3) * proporcion


def _elegir_producto(rng, productos, offset):
    pesos = [_peso_producto(p[1], offset) for p in productos]
    return rng.choices(productos, weights=pesos)[0]


def _insertar_venta(conn, fecha, cliente_id, producto, rng):
    cantidad = rng.choices([1, 2, 3], weights=[70, 25, 5])[0]
    conn.execute(
        "INSERT INTO ventas (fecha, cliente_id, producto_id, cantidad, precio_unitario) "
        "VALUES (?, ?, ?, ?, ?)",
        (fecha.isoformat(), cliente_id, producto[0], cantidad, producto[2]),
    )


def generar_ventas(conn, rng, cliente_ids, hoy):
    productos = conn.execute("SELECT id, nombre, precio_venta FROM productos ORDER BY id").fetchall()

    inactivos = set(rng.sample(cliente_ids, NUM_CLIENTES_INACTIVOS))
    activos = [c for c in cliente_ids if c not in inactivos]

    # aseguramos historial de compras de los clientes inactivos antes del corte,
    # para que cumplan el minimo_compras exigido por clientes_inactivos
    for cliente_id in inactivos:
        for _ in range(rng.randint(4, 7)):
            offset = rng.randint(CORTE_INACTIVIDAD, DIAS_HISTORIA - 1)
            fecha = hoy - timedelta(days=offset)
            producto = _elegir_producto(rng, productos, offset)
            _insertar_venta(conn, fecha, cliente_id, producto, rng)

    for offset in range(DIAS_HISTORIA - 1, -1, -1):
        fecha = hoy - timedelta(days=offset)
        num_ventas = round(BASE_VENTAS_DIA * MULTIPLICADOR_DIA[fecha.weekday()])
        pool_clientes = activos if offset < CORTE_INACTIVIDAD else cliente_ids
        for _ in range(num_ventas):
            producto = _elegir_producto(rng, productos, offset)
            cliente_id = None if rng.random() < PROB_SIN_CLIENTE else rng.choice(pool_clientes)
            _insertar_venta(conn, fecha, cliente_id, producto, rng)


def poblar(conn, hoy=None):
    """Vacia y vuelve a llenar la base con los datos semilla."""
    hoy = hoy if hoy is not None else date.today()
    rng = random.Random(SEMILLA)

    limpiar_tablas(conn)
    cargar_insumos(conn)
    cargar_productos(conn)
    cargar_recetas(conn)
    conn.commit()

    cliente_ids = generar_clientes(conn, rng, hoy)
    generar_ventas(conn, rng, cliente_ids, hoy)
    conn.commit()


def main(path: Path | None = None):
    init_db(path)
    conn = get_conn(path)
    try:
        poblar(conn)
    finally:
        conn.close()
    print(
        f"listo: {NUM_CLIENTES} clientes, 10 productos, 12 insumos, "
        f"{DIAS_HISTORIA} dias de ventas"
    )


if __name__ == "__main__":
    main()
