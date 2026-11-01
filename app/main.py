"""Punto de entrada: crea la app, registra routers y manejadores de errores."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routers import cuentas, health
from app.core.config import get_settings
from app.core.exceptions import CuentaNoEncontradaError

logger = logging.getLogger("cuentas_api")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.include_router(health.router)
    app.include_router(cuentas.router)

    @app.exception_handler(CuentaNoEncontradaError)
    async def cuenta_no_encontrada(_: Request, exc: CuentaNoEncontradaError) -> JSONResponse:
        logger.info("Cuenta no encontrada o ajena: %s", exc.cuenta_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Cuenta no encontrada"},
        )

    @app.exception_handler(Exception)
    async def error_inesperado(_: Request, exc: Exception) -> JSONResponse:
        # No se devuelven detalles internos al cliente; quedan en el log
        logger.exception("Error inesperado", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno"},
        )

    return app


app = create_app()
