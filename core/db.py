"""Conexion y esquema de la base de datos de la cafeteria."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/cafeteria.db")

DDL = """
CREATE TABLE IF NOT EXISTS insumos (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE,
  unidad        TEXT NOT NULL,          -- kg, litro, unidad
  stock_actual  REAL NOT NULL,
  stock_minimo  REAL NOT NULL,
  costo_unitario REAL NOT NULL,
  proveedor     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productos (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE,
  precio_venta  REAL NOT NULL,
  categoria     TEXT NOT NULL           -- batido, bowl, cafe, snack
);

CREATE TABLE IF NOT EXISTS recetas (
  producto_id   INTEGER NOT NULL REFERENCES productos(id),
  insumo_id     INTEGER NOT NULL REFERENCES insumos(id),
  cantidad      REAL NOT NULL,          -- en la unidad del insumo
  PRIMARY KEY (producto_id, insumo_id)
);

CREATE TABLE IF NOT EXISTS clientes (
  id            INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL,
  fecha_registro DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas (
  id            INTEGER PRIMARY KEY,
  fecha         DATE NOT NULL,
  cliente_id    INTEGER REFERENCES clientes(id),  -- NULL = venta sin cliente
  producto_id   INTEGER NOT NULL REFERENCES productos(id),
  cantidad      INTEGER NOT NULL,
  precio_unitario REAL NOT NULL          -- congelado al momento de la venta
);

CREATE TABLE IF NOT EXISTS ordenes_compra (
  id            INTEGER PRIMARY KEY,
  fecha         DATE NOT NULL,
  proveedor     TEXT NOT NULL,
  estado        TEXT NOT NULL,           -- propuesta, aprobada, rechazada
  aprobada_por  TEXT,
  aprobada_en   TIMESTAMP,
  detalle_json  TEXT NOT NULL            -- items y cantidades
);
"""


def get_conn(path: Path | None = None) -> sqlite3.Connection:
    """Abre una conexion a la base de datos y activa las foreign keys."""
    ruta = path if path is not None else DB_PATH
    conn = sqlite3.connect(ruta)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> None:
    """Crea la carpeta de datos si falta y ejecuta el DDL del esquema."""
    ruta = path if path is not None else DB_PATH
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn(ruta)
    try:
        conn.executescript(DDL)
        conn.commit()
    finally:
        conn.close()
