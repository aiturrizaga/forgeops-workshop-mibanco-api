"""Modelos Pydantic de salida del API (contrato con el frontend)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

from app.models.cuenta import Cuenta, Moneda, Movimiento, TipoCuenta, TipoMovimiento

# Los montos se manejan como Decimal y se envían como número en el JSON
Monto = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class CuentaOut(BaseModel):
    """Datos de la cuenta SIN saldos (minimización de datos).

    Los saldos solo viajan por GET /api/cuentas/saldos, cuando el usuario
    pulsa «Mostrar saldos».
    """

    id: str
    tipo: TipoCuenta
    alias: str
    numero_enmascarado: str
    moneda: Moneda

    @classmethod
    def desde_entidad(cls, cuenta: Cuenta) -> "CuentaOut":
        return cls(
            id=cuenta.id,
            tipo=cuenta.tipo,
            alias=cuenta.alias,
            numero_enmascarado=cuenta.numero_enmascarado,
            moneda=cuenta.moneda,
        )


class SaldoCuentaOut(BaseModel):
    cuenta_id: str
    moneda: Moneda
    saldo_disponible: Monto
    saldo_contable: Monto

    @classmethod
    def desde_entidad(cls, cuenta: Cuenta) -> "SaldoCuentaOut":
        return cls(
            cuenta_id=cuenta.id,
            moneda=cuenta.moneda,
            saldo_disponible=cuenta.saldo_disponible,
            saldo_contable=cuenta.saldo_contable,
        )


class TotalMonedaOut(BaseModel):
    moneda: Moneda
    saldo_disponible: Monto


class SaldosResponse(BaseModel):
    saldos: list[SaldoCuentaOut]
    # Total disponible por moneda, sin tarjetas de crédito (son línea, no saldo)
    totales: list[TotalMonedaOut]


class MovimientoOut(BaseModel):
    id: str
    fecha: date
    descripcion: str
    comercio: str | None
    categoria: str
    monto: Monto
    tipo: TipoMovimiento

    @classmethod
    def desde_entidad(cls, movimiento: Movimiento) -> "MovimientoOut":
        return cls(
            id=movimiento.id,
            fecha=movimiento.fecha,
            descripcion=movimiento.descripcion,
            comercio=movimiento.comercio,
            categoria=movimiento.categoria,
            monto=movimiento.monto,
            tipo=movimiento.tipo,
        )


class CuentasResponse(BaseModel):
    cuentas: list[CuentaOut]


class MovimientosResponse(BaseModel):
    cuenta: CuentaOut
    movimientos: list[MovimientoOut]


class ErrorResponse(BaseModel):
    detail: str
