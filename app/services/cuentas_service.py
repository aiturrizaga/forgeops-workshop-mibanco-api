"""Lógica de negocio de cuentas y movimientos."""

import logging

from app.core.exceptions import CuentaNoEncontradaError
from app.models.cuenta import Cuenta, Movimiento
from app.repositories.base import CuentasRepository
from app.services.generador_demo import GeneradorDatosDemo

logger = logging.getLogger("cuentas_api")


class CuentasService:
    def __init__(self, repositorio: CuentasRepository, generador: GeneradorDatosDemo) -> None:
        self._repositorio = repositorio
        self._generador = generador

    def registrar_acceso(self, usuario: str) -> None:
        """Da de alta al usuario con datos demo la primera vez; luego solo registra el acceso."""
        creado = self._repositorio.registrar_acceso(
            usuario, lambda: self._generador.cuentas_para(usuario)
        )
        if creado:
            logger.info(
                "Usuario nuevo %s: plantilla %s", usuario, self._generador.plantilla_para(usuario)
            )

    def listar_cuentas(self, usuario: str) -> list[Cuenta]:
        return self._repositorio.listar_por_usuario(usuario)

    def obtener_cuenta(self, usuario: str, cuenta_id: str) -> Cuenta:
        cuenta = self._repositorio.obtener_de_usuario(usuario, cuenta_id)
        if cuenta is None:
            # Cuenta inexistente o de otro usuario: mismo error para no filtrar datos
            raise CuentaNoEncontradaError(cuenta_id)
        return cuenta

    def listar_movimientos(self, usuario: str, cuenta_id: str) -> tuple[Cuenta, list[Movimiento]]:
        """Devuelve la cuenta y sus movimientos, del más reciente al más antiguo."""
        cuenta = self.obtener_cuenta(usuario, cuenta_id)
        movimientos = sorted(cuenta.movimientos, key=lambda m: (m.fecha, m.id), reverse=True)
        return cuenta, movimientos
