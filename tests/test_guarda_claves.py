# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Si cambia la clave maestra, la API falla ANTES de consumir emisiones o firmar checkpoints."""
import secrets

import pytest
from fastapi.testclient import TestClient

import main
from helpers_api import crear_conv, emitir_token, votar
from tests_db import emisiones


@pytest.fixture
def cambiar_clave(monkeypatch):
    """Simula un reinicio con otra clave maestra (p. ej. clave efímera nueva)."""
    def _cambiar():
        monkeypatch.setattr(main, "_MASTER", secrets.token_bytes(32))
        main._emisores.clear()
    return _cambiar


def test_con_otra_clave_inicio_da_503_sin_consumir_emision(api, cambiar_clave):
    cid = crear_conv(api, ["p1"])
    cambiar_clave()
    r = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
    assert r.status_code == 503 and "clave del servidor" in r.json()["detail"]
    assert emisiones() == []                                       # no se creó ninguna fila: el votante no pierde su emisión


def test_con_otra_clave_votar_y_sellar_y_cerrar_dan_503(api, cambiar_clave, monkeypatch):
    cid = crear_conv(api, ["p1", "p2"])
    R, s = emitir_token(api, cid, "p1", "a_favor")
    assert votar(api, cid, "a_favor", R, s).status_code == 200
    cambiar_clave()
    R2, s2 = R, s
    assert votar(api, cid, "a_favor", R2, s2).status_code == 503
    assert api.client.post(f"/convocatorias/{cid}/registro/sellar", headers=api.admin).status_code == 503
    assert api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": "cerrada"}).status_code == 503
    assert api.client.get(f"/convocatorias/{cid}").json()["estado"] == "emision"   # el cierre se revirtió: no se firmó nada con la clave errónea
    assert api.client.get(f"/convocatorias/{cid}/registro").json()["checkpoints"] == []


def test_restaurar_la_clave_correcta_restablece_el_servicio(api, monkeypatch):
    cid = crear_conv(api, ["p1"])
    original = main._MASTER
    monkeypatch.setattr(main, "_MASTER", secrets.token_bytes(32)); main._emisores.clear()
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"}).status_code == 503
    monkeypatch.setattr(main, "_MASTER", original); main._emisores.clear()
    R, s = emitir_token(api, cid, "p1", "a_favor")
    assert votar(api, cid, "a_favor", R, s).status_code == 200


def test_con_la_clave_correcta_nada_cambia(api):
    cid = crear_conv(api, ["p1"])
    assert main._claves_coinciden(cid, *[api.client.get(f"/convocatorias/{cid}").json()[k] for k in ("emisor_pub_hex", "log_pub_hex")])


def test_aviso_al_arrancar_y_modo_estricto(api, cambiar_clave, capfd, monkeypatch):
    crear_conv(api, ["p1"])
    cambiar_clave()
    with TestClient(main.app):                                      # dispara el arranque (lifespan)
        pass
    err = capfd.readouterr().err
    assert "ADVERTENCIA" in err and "NO corresponde" in err
    monkeypatch.setenv("PANRAP_ESTRICTO", "1")
    with pytest.raises(RuntimeError, match="PANRAP_ESTRICTO"):
        with TestClient(main.app):
            pass


def test_arranque_sin_problemas_no_avisa(api, capfd):
    crear_conv(api, ["p1"])
    with TestClient(main.app):
        pass
    assert "NO corresponde" not in capfd.readouterr().err
