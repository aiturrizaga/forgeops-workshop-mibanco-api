"""Endpoints de cuentas y movimientos del usuario autenticado."""

from fastapi import APIRouter, status

from app.api.dependencies import CuentasServiceDep, UsuarioActual
from app.schemas.cuenta import (
    CuentaOut,
    CuentasResponse,
    ErrorResponse,
    MovimientoOut,
    MovimientosResponse,
)

router = APIRouter(
    prefix="/api/cuentas",
    tags=["cuentas"],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)


@router.get("", response_model=CuentasResponse)
def listar_cuentas(usuario: UsuarioActual, servicio: CuentasServiceDep) -> CuentasResponse:
    cuentas = servicio.listar_cuentas(usuario)
    return CuentasResponse(cuentas=[CuentaOut.desde_entidad(c) for c in cuentas])


@router.get(
    "/{cuenta_id}/movimientos",
    response_model=MovimientosResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def listar_movimientos(
    cuenta_id: str, usuario: UsuarioActual, servicio: CuentasServiceDep
) -> MovimientosResponse:
    cuenta, movimientos = servicio.listar_movimientos(usuario, cuenta_id)
    return MovimientosResponse(
        cuenta=CuentaOut.desde_entidad(cuenta),
        movimientos=[MovimientoOut.desde_entidad(m) for m in movimientos],
    )
