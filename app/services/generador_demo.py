"""Genera las cuentas iniciales de un usuario nuevo a partir de una plantilla."""

import hashlib
import random
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import date

from app.models.cuenta import Cuenta


class GeneradorDatosDemo:
    def __init__(self, plantillas: dict[str, list[Cuenta]], hoy: Callable[[], date] = date.today) -> None:
        # Orden fijo para que la elección por sub sea siempre la misma
        self._plantillas = dict(sorted(plantillas.items()))
        self._hoy = hoy

    def plantilla_para(self, usuario: str) -> str:
        """Elige una plantilla de forma determinista a partir del sub del usuario."""
        indice = int(hashlib.sha256(usuario.encode()).hexdigest(), 16) % len(self._plantillas)
        return list(self._plantillas)[indice]

    def cuentas_para(self, usuario: str) -> list[Cuenta]:
        """Copia la plantilla con ids y números nuevos, y fechas recientes."""
        cuentas = self._plantillas[self.plantilla_para(usuario)]
        # El movimiento más reciente de la plantilla pasa a ser "hoy"
        ultima_fecha = max((m.fecha for c in cuentas for m in c.movimientos), default=self._hoy())
        desfase = self._hoy() - ultima_fecha
        azar = random.Random(usuario)  # números de cuenta estables por usuario

        return [
            replace(
                cuenta,
                id=f"c-{uuid.uuid4().hex[:12]}",
                numero=_nuevo_numero(cuenta.numero, azar),
                movimientos=tuple(
                    replace(m, id=f"m-{uuid.uuid4().hex[:12]}", fecha=m.fecha + desfase)
                    for m in cuenta.movimientos
                ),
            )
            for cuenta in cuentas
        ]


def _nuevo_numero(numero: str, azar: random.Random) -> str:
    """Reemplaza los dígitos manteniendo el formato (guiones y longitud)."""
    return "".join(str(azar.randint(0, 9)) if c.isdigit() else c for c in numero)
