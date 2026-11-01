"""Dependencias de FastAPI: usuario actual y servicio de cuentas.

IMPORTANTE (seguridad): este servicio NO valida tokens. Confía en la cabecera
X-Usuario que agrega PingGateway después de validar el access token contra AM.
Esto solo es seguro porque:
  - el servicio es un Service ClusterIP sin Ingress, inaccesible desde Internet;
  - la ruta de IG elimina cualquier X-Usuario que envíe el cliente antes de
    agregar el suyo.
Si alguien pudiera llamar al servicio directamente, podría hacerse pasar por
cualquier usuario enviando esa cabecera.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.repositories.plantillas import cargar_plantillas
from app.repositories.sqlite_repository import SqliteCuentasRepository
from app.services.cuentas_service import CuentasService
from app.services.generador_demo import GeneradorDatosDemo


@lru_cache
def get_cuentas_service() -> CuentasService:
    """Crea el servicio una sola vez (abre la base y lee las plantillas)."""
    settings = get_settings()
    repositorio = SqliteCuentasRepository(settings.database_path)
    generador = GeneradorDatosDemo(cargar_plantillas(settings.plantillas_path))
    return CuentasService(repositorio, generador)


CuentasServiceDep = Annotated[CuentasService, Depends(get_cuentas_service)]


def get_usuario_actual(request: Request, servicio: CuentasServiceDep) -> str:
    """Obtiene el sub desde X-Usuario (401 si falta) y registra el acceso.

    El primer acceso de un usuario lo da de alta con datos demo; los siguientes
    solo actualizan su último acceso.
    """
    usuario = request.headers.get(get_settings().usuario_header, "").strip()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no identificado",
        )
    servicio.registrar_acceso(usuario)
    return usuario


UsuarioActual = Annotated[str, Depends(get_usuario_actual)]
