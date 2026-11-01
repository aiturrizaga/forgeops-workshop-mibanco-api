"""Repositorio de cuentas sobre SQLite (solo para la demo).

Se abre una conexión por operación: es simple, segura entre hilos (FastAPI
ejecuta los endpoints síncronos en un pool de hilos) y suficiente para una
sola réplica. Los montos se guardan como texto para no perder precisión.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from app.models.cuenta import Cuenta, Moneda, Movimiento, TipoCuenta, TipoMovimiento

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    sub           TEXT PRIMARY KEY,   -- identificador del usuario en AM (X-Usuario)
    creado_en     TEXT NOT NULL,
    ultimo_acceso TEXT NOT NULL,
    accesos       INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cuentas (
    id               TEXT PRIMARY KEY,
    sub              TEXT NOT NULL REFERENCES usuarios(sub) ON DELETE CASCADE,
    orden            INTEGER NOT NULL,
    tipo             TEXT NOT NULL,
    alias            TEXT NOT NULL,
    numero           TEXT NOT NULL,
    moneda           TEXT NOT NULL,
    saldo_disponible TEXT NOT NULL,
    saldo_contable   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cuentas_sub ON cuentas(sub);
CREATE TABLE IF NOT EXISTS movimientos (
    id          TEXT PRIMARY KEY,
    cuenta_id   TEXT NOT NULL REFERENCES cuentas(id) ON DELETE CASCADE,
    fecha       TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    comercio    TEXT,
    categoria   TEXT NOT NULL,
    monto       TEXT NOT NULL,
    tipo        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_movimientos_cuenta ON movimientos(cuenta_id);
"""


class SqliteCuentasRepository:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conn:
            # WAL permite leer mientras otro hilo escribe
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(ESQUEMA)

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        # isolation_level=None: las transacciones se abren explícitamente con BEGIN
        conn = sqlite3.connect(self._ruta, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def registrar_acceso(self, usuario: str, cuentas_iniciales: Callable[[], list[Cuenta]]) -> bool:
        ahora = datetime.now(UTC).isoformat(timespec="seconds")
        with self._conexion() as conn:
            # BEGIN IMMEDIATE serializa a los escritores: si llegan dos primeras
            # peticiones a la vez, la segunda espera y ya encuentra al usuario creado
            conn.execute("BEGIN IMMEDIATE")
            try:
                actualizado = conn.execute(
                    "UPDATE usuarios SET ultimo_acceso = ?, accesos = accesos + 1 WHERE sub = ?",
                    (ahora, usuario),
                ).rowcount
                if actualizado:
                    conn.execute("COMMIT")
                    return False
                conn.execute(
                    "INSERT INTO usuarios (sub, creado_en, ultimo_acceso) VALUES (?, ?, ?)",
                    (usuario, ahora, ahora),
                )
                for orden, cuenta in enumerate(cuentas_iniciales()):
                    self._insertar_cuenta(conn, usuario, orden, cuenta)
                conn.execute("COMMIT")
                return True
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def listar_por_usuario(self, usuario: str) -> list[Cuenta]:
        with self._conexion() as conn:
            filas = conn.execute(
                "SELECT * FROM cuentas WHERE sub = ? ORDER BY orden", (usuario,)
            ).fetchall()
            return [self._a_cuenta(conn, fila) for fila in filas]

    def obtener_de_usuario(self, usuario: str, cuenta_id: str) -> Cuenta | None:
        with self._conexion() as conn:
            # El filtro por sub garantiza que nunca se devuelva una cuenta ajena
            fila = conn.execute(
                "SELECT * FROM cuentas WHERE id = ? AND sub = ?", (cuenta_id, usuario)
            ).fetchone()
            return self._a_cuenta(conn, fila) if fila else None

    @staticmethod
    def _insertar_cuenta(conn: sqlite3.Connection, usuario: str, orden: int, cuenta: Cuenta) -> None:
        conn.execute(
            "INSERT INTO cuentas (id, sub, orden, tipo, alias, numero, moneda,"
            " saldo_disponible, saldo_contable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cuenta.id,
                usuario,
                orden,
                cuenta.tipo.value,
                cuenta.alias,
                cuenta.numero,
                cuenta.moneda.value,
                str(cuenta.saldo_disponible),
                str(cuenta.saldo_contable),
            ),
        )
        conn.executemany(
            "INSERT INTO movimientos (id, cuenta_id, fecha, descripcion, comercio, categoria,"
            " monto, tipo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    m.id,
                    cuenta.id,
                    m.fecha.isoformat(),
                    m.descripcion,
                    m.comercio,
                    m.categoria,
                    str(m.monto),
                    m.tipo.value,
                )
                for m in cuenta.movimientos
            ],
        )

    @staticmethod
    def _a_cuenta(conn: sqlite3.Connection, fila: sqlite3.Row) -> Cuenta:
        movimientos = conn.execute(
            "SELECT * FROM movimientos WHERE cuenta_id = ?", (fila["id"],)
        ).fetchall()
        return Cuenta(
            id=fila["id"],
            tipo=TipoCuenta(fila["tipo"]),
            alias=fila["alias"],
            numero=fila["numero"],
            moneda=Moneda(fila["moneda"]),
            saldo_disponible=Decimal(fila["saldo_disponible"]),
            saldo_contable=Decimal(fila["saldo_contable"]),
            movimientos=tuple(
                Movimiento(
                    id=m["id"],
                    fecha=date.fromisoformat(m["fecha"]),
                    descripcion=m["descripcion"],
                    comercio=m["comercio"],
                    categoria=m["categoria"],
                    monto=Decimal(m["monto"]),
                    tipo=TipoMovimiento(m["tipo"]),
                )
                for m in movimientos
            ),
        )
