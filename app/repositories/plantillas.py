"""Carga las plantillas de datos demo desde data/plantillas.json.

Estructura esperada del archivo:
    {"plantillas": {"<nombre>": {"cuentas": [{..., "movimientos": [...]}]}}}
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.models.cuenta import Cuenta, Moneda, Movimiento, TipoCuenta, TipoMovimiento


def cargar_plantillas(ruta: Path) -> dict[str, list[Cuenta]]:
    """Devuelve las cuentas de cada plantilla, por nombre de plantilla."""
    with ruta.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    plantillas = {
        nombre: [_a_cuenta(c) for c in info.get("cuentas", [])]
        for nombre, info in datos.get("plantillas", {}).items()
    }
    if not plantillas:
        raise ValueError(f"No hay plantillas en {ruta}")
    return plantillas


def _a_cuenta(datos: dict[str, Any]) -> Cuenta:
    return Cuenta(
        id=datos["id"],
        tipo=TipoCuenta(datos["tipo"]),
        alias=datos["alias"],
        numero=datos["numero"],
        moneda=Moneda(datos["moneda"]),
        saldo_disponible=Decimal(str(datos["saldo_disponible"])),
        saldo_contable=Decimal(str(datos["saldo_contable"])),
        movimientos=tuple(_a_movimiento(m) for m in datos.get("movimientos", [])),
    )


def _a_movimiento(datos: dict[str, Any]) -> Movimiento:
    return Movimiento(
        id=datos["id"],
        fecha=date.fromisoformat(datos["fecha"]),
        descripcion=datos["descripcion"],
        comercio=datos.get("comercio"),
        categoria=datos["categoria"],
        monto=Decimal(str(datos["monto"])),
        tipo=TipoMovimiento(datos["tipo"]),
    )
