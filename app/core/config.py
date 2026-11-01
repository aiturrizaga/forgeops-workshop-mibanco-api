"""Configuración del servicio leída desde variables de entorno.

Todas las variables usan el prefijo CUENTAS_ (por ejemplo CUENTAS_DATABASE_PATH).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del proyecto (carpeta que contiene app/ y data/)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CUENTAS_", env_file=".env", extra="ignore")

    app_name: str = "MiBanco Cuentas API (demo)"
    # Plantillas de datos demo que se copian a cada usuario nuevo
    plantillas_path: Path = BASE_DIR / "data" / "plantillas.json"
    # Base SQLite; en Kubernetes vive en un volumen persistente montado en /srv/var
    database_path: Path = BASE_DIR / "var" / "cuentas.db"
    # Cabecera que agrega PingGateway con el sub (UUID) del usuario autenticado
    usuario_header: str = "X-Usuario"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración (se crea una sola vez por proceso)."""
    return Settings()
