"""Fixtures compartidas por las pruebas. Cada prueba usa su propia base SQLite."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_cuentas_service
from app.core.config import get_settings
from app.main import app
from app.repositories.plantillas import cargar_plantillas
from app.repositories.sqlite_repository import SqliteCuentasRepository
from app.services.cuentas_service import CuentasService
from app.services.generador_demo import GeneradorDatosDemo

HOY = date(2026, 11, 1)

# Dos subs de ejemplo con el formato de AM (UUID)
ANA = "f71ef34c-4e60-4418-9067-90ea953169db"
LUIS = "0b6c2f1e-9a1d-4a55-8c1e-3f2d7a9b4c10"


@pytest.fixture
def repositorio(tmp_path: Path) -> SqliteCuentasRepository:
    return SqliteCuentasRepository(tmp_path / "cuentas.db")


@pytest.fixture
def generador() -> GeneradorDatosDemo:
    return GeneradorDatosDemo(cargar_plantillas(get_settings().plantillas_path), hoy=lambda: HOY)


@pytest.fixture
def servicio(repositorio: SqliteCuentasRepository, generador: GeneradorDatosDemo) -> CuentasService:
    return CuentasService(repositorio, generador)


@pytest.fixture
def client(servicio: CuentasService):
    app.dependency_overrides[get_cuentas_service] = lambda: servicio
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def como(client: TestClient):
    """Devuelve una función que hace GET como si IG hubiera agregado X-Usuario."""

    def _get(usuario: str, url: str):
        return client.get(url, headers={"X-Usuario": usuario})

    return _get
