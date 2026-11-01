"""Interfaz del repositorio de cuentas.

Los servicios dependen de esta interfaz y no de la implementación concreta
(hoy SQLite), así se puede cambiar por otra base de datos sin tocar la lógica.
"""

from collections.abc import Callable
from typing import Protocol

from app.models.cuenta import Cuenta


class CuentasRepository(Protocol):
    def registrar_acceso(self, usuario: str, cuentas_iniciales: Callable[[], list[Cuenta]]) -> bool:
        """Registra un acceso del usuario.

        Si el usuario no existe, lo crea junto con las cuentas que devuelve
        `cuentas_iniciales` (en la misma transacción) y devuelve True. Si ya
        existe, actualiza su último acceso y devuelve False.
        """
        ...

    def listar_por_usuario(self, usuario: str) -> list[Cuenta]:
        """Devuelve las cuentas del usuario con sus movimientos (vacía si no tiene)."""
        ...

    def obtener_de_usuario(self, usuario: str, cuenta_id: str) -> Cuenta | None:
        """Devuelve la cuenta solo si pertenece al usuario; si no, None."""
        ...
