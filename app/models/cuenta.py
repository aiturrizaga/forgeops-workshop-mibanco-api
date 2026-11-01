"""Entidades de dominio. No dependen de FastAPI ni de Pydantic."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TipoCuenta(StrEnum):
    AHORROS = "AHORROS"
    CORRIENTE = "CORRIENTE"
    TARJETA_CREDITO = "TARJETA_CREDITO"


class Moneda(StrEnum):
    PEN = "PEN"
    USD = "USD"


class TipoMovimiento(StrEnum):
    CARGO = "CARGO"
    ABONO = "ABONO"


@dataclass(frozen=True)
class Movimiento:
    id: str
    fecha: date
    descripcion: str
    comercio: str | None
    categoria: str
    monto: Decimal  # siempre positivo; el signo lo da el tipo
    tipo: TipoMovimiento


@dataclass(frozen=True)
class Cuenta:
    id: str
    tipo: TipoCuenta
    alias: str
    numero: str  # número completo; nunca sale del servicio sin enmascarar
    moneda: Moneda
    saldo_disponible: Decimal
    saldo_contable: Decimal
    movimientos: tuple[Movimiento, ...] = ()

    @property
    def numero_enmascarado(self) -> str:
        """Muestra solo los últimos 4 dígitos, por ejemplo ****-****-1234."""
        digitos = "".join(c for c in self.numero if c.isdigit())
        return f"****-****-{digitos[-4:]}"
