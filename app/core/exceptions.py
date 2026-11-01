"""Excepciones de dominio. main.py las traduce a respuestas HTTP."""


class CuentaNoEncontradaError(Exception):
    """La cuenta no existe o no pertenece al usuario actual.

    Ambos casos se tratan igual (404) para no revelar si la cuenta existe.
    """

    def __init__(self, cuenta_id: str) -> None:
        super().__init__(f"Cuenta no encontrada: {cuenta_id}")
        self.cuenta_id = cuenta_id
