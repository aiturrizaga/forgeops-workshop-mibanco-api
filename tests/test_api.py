"""Pruebas de los endpoints HTTP."""

from fastapi.testclient import TestClient

from tests.conftest import ANA, LUIS


def test_health(client: TestClient) -> None:
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_sin_x_usuario_responde_401(client: TestClient) -> None:
    assert client.get("/api/cuentas").status_code == 401


def test_x_usuario_vacio_responde_401(client: TestClient) -> None:
    assert client.get("/api/cuentas", headers={"X-Usuario": "  "}).status_code == 401


def test_lista_de_cuentas_no_incluye_saldos_ni_numero_completo(como) -> None:
    respuesta = como(ANA, "/api/cuentas")
    assert respuesta.status_code == 200
    cuentas = respuesta.json()["cuentas"]
    assert len(cuentas) >= 2
    # Minimización de datos: los saldos solo llegan por /api/cuentas/saldos
    assert set(cuentas[0]) == {"id", "tipo", "alias", "numero_enmascarado", "moneda"}


def test_saldos_de_las_cuentas_propias_y_totales_sin_tarjetas(como) -> None:
    cuentas = como(ANA, "/api/cuentas").json()["cuentas"]
    cuerpo = como(ANA, "/api/cuentas/saldos").json()

    assert {s["cuenta_id"] for s in cuerpo["saldos"]} == {c["id"] for c in cuentas}
    assert set(cuerpo["saldos"][0]) == {"cuenta_id", "moneda", "saldo_disponible", "saldo_contable"}

    tipos = {c["id"]: c["tipo"] for c in cuentas}
    esperado: dict[str, float] = {}
    for s in cuerpo["saldos"]:
        if tipos[s["cuenta_id"]] != "TARJETA_CREDITO":
            esperado[s["moneda"]] = round(esperado.get(s["moneda"], 0) + s["saldo_disponible"], 2)
    assert {t["moneda"]: t["saldo_disponible"] for t in cuerpo["totales"]} == esperado


def test_saldos_no_mezclan_usuarios(como) -> None:
    ids_luis = {c["id"] for c in como(LUIS, "/api/cuentas").json()["cuentas"]}
    saldos_ana = {s["cuenta_id"] for s in como(ANA, "/api/cuentas/saldos").json()["saldos"]}
    assert saldos_ana.isdisjoint(ids_luis)


def test_saldos_sin_x_usuario_responde_401(client: TestClient) -> None:
    assert client.get("/api/cuentas/saldos").status_code == 401


def test_respuestas_del_api_no_se_cachean(como) -> None:
    assert como(ANA, "/api/cuentas/saldos").headers["cache-control"] == "no-store"
    assert como(ANA, "/api/cuentas").headers["cache-control"] == "no-store"


def test_segundo_acceso_devuelve_lo_mismo(como) -> None:
    primero = como(ANA, "/api/cuentas").json()
    assert como(ANA, "/api/cuentas").json() == primero


def test_movimientos_de_cuenta_propia(como) -> None:
    cuenta_id = como(ANA, "/api/cuentas").json()["cuentas"][0]["id"]
    respuesta = como(ANA, f"/api/cuentas/{cuenta_id}/movimientos")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["cuenta"]["id"] == cuenta_id
    assert len(cuerpo["movimientos"]) == 10
    primero = cuerpo["movimientos"][0]
    assert set(primero) == {"id", "fecha", "descripcion", "comercio", "categoria", "monto", "tipo"}
    assert primero["tipo"] in {"CARGO", "ABONO"}


def test_cuenta_de_otro_usuario_responde_404(como) -> None:
    cuenta_luis = como(LUIS, "/api/cuentas").json()["cuentas"][0]["id"]
    respuesta = como(ANA, f"/api/cuentas/{cuenta_luis}/movimientos")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Cuenta no encontrada"}


def test_cuenta_inexistente_responde_404(como) -> None:
    assert como(ANA, "/api/cuentas/no-existe/movimientos").status_code == 404
