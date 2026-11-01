"""Pruebas de la lógica de negocio y del repositorio SQLite (sin HTTP)."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core.exceptions import CuentaNoEncontradaError
from app.repositories.sqlite_repository import SqliteCuentasRepository
from app.services.cuentas_service import CuentasService
from app.services.generador_demo import GeneradorDatosDemo
from tests.conftest import ANA, HOY, LUIS


def test_usuario_nuevo_recibe_las_cuentas_de_su_plantilla(
    servicio: CuentasService, generador: GeneradorDatosDemo
) -> None:
    servicio.registrar_acceso(ANA)
    cuentas = servicio.listar_cuentas(ANA)
    plantilla = generador.plantilla_para(ANA)
    assert plantilla in {"personal", "familiar", "negocio"}
    assert len(cuentas) >= 2
    assert all(len(c.movimientos) == 10 for c in cuentas)


def test_reingreso_conserva_los_mismos_datos(servicio: CuentasService) -> None:
    servicio.registrar_acceso(ANA)
    primeras = [c.id for c in servicio.listar_cuentas(ANA)]
    servicio.registrar_acceso(ANA)
    assert [c.id for c in servicio.listar_cuentas(ANA)] == primeras


def test_reingreso_actualiza_ultimo_acceso_y_contador(
    servicio: CuentasService, repositorio: SqliteCuentasRepository, tmp_path: Path
) -> None:
    servicio.registrar_acceso(ANA)
    servicio.registrar_acceso(ANA)
    servicio.registrar_acceso(ANA)
    with sqlite3.connect(tmp_path / "cuentas.db") as conn:
        accesos, creado, ultimo = conn.execute(
            "SELECT accesos, creado_en, ultimo_acceso FROM usuarios WHERE sub = ?", (ANA,)
        ).fetchone()
    assert accesos == 3
    assert ultimo >= creado


def test_usuario_sin_acceso_no_tiene_cuentas(servicio: CuentasService) -> None:
    assert servicio.listar_cuentas("desconocido") == []


def test_ids_y_numeros_son_propios_de_cada_usuario(servicio: CuentasService) -> None:
    servicio.registrar_acceso(ANA)
    servicio.registrar_acceso(LUIS)
    ids_ana = {c.id for c in servicio.listar_cuentas(ANA)}
    ids_luis = {c.id for c in servicio.listar_cuentas(LUIS)}
    assert ids_ana.isdisjoint(ids_luis)


def test_numero_se_enmascara(servicio: CuentasService) -> None:
    servicio.registrar_acceso(ANA)
    cuenta = servicio.listar_cuentas(ANA)[0]
    assert cuenta.numero_enmascarado == f"****-****-{cuenta.numero.replace('-', '')[-4:]}"


def test_movimientos_recientes_y_ordenados(servicio: CuentasService) -> None:
    servicio.registrar_acceso(ANA)
    cuenta_id = servicio.listar_cuentas(ANA)[0].id
    _, movimientos = servicio.listar_movimientos(ANA, cuenta_id)
    fechas = [m.fecha for m in movimientos]
    assert fechas == sorted(fechas, reverse=True)
    assert max(fechas) <= HOY


def test_cuenta_de_otro_usuario_no_se_encuentra(servicio: CuentasService) -> None:
    servicio.registrar_acceso(ANA)
    servicio.registrar_acceso(LUIS)
    cuenta_luis = servicio.listar_cuentas(LUIS)[0].id
    with pytest.raises(CuentaNoEncontradaError):
        servicio.listar_movimientos(ANA, cuenta_luis)


def test_la_plantilla_se_elige_siempre_igual(generador: GeneradorDatosDemo) -> None:
    assert generador.plantilla_para(ANA) == generador.plantilla_para(ANA)


def test_primeros_accesos_simultaneos_crean_un_solo_juego_de_cuentas(
    servicio: CuentasService, generador: GeneradorDatosDemo, tmp_path: Path
) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: servicio.registrar_acceso(ANA), range(8)))
    # Mismo número de cuentas que la plantilla: no se duplicaron
    assert len(servicio.listar_cuentas(ANA)) == len(generador.cuentas_para(ANA))
    with sqlite3.connect(tmp_path / "cuentas.db") as conn:
        (accesos,) = conn.execute("SELECT accesos FROM usuarios WHERE sub = ?", (ANA,)).fetchone()
    assert accesos == 8
