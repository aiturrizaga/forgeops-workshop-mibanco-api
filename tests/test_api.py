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


def test_primer_acceso_crea_cuentas_y_no_expone_el_numero(como) -> None:
    respuesta = como(ANA, "/api/cuentas")
    assert respuesta.status_code == 200
    cuentas = respuesta.json()["cuentas"]
    assert len(cuentas) >= 2
    assert all("numero" not in c for c in cuentas)
    assert set(cuentas[0]) == {
        "id",
        "tipo",
        "alias",
        "numero_enmascarado",
        "moneda",
        "saldo_disponible",
        "saldo_contable",
    }


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
