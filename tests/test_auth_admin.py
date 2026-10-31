# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""T3: ningún endpoint administrativo funciona sin token; los públicos no lo exigen."""
import pytest

from helpers_api import crear_conv

VALIDA = {"titulo": "t", "texto": "x"}
RUTAS_ADMIN = [
    ("post", "/convocatorias", VALIDA),
    ("patch", "/convocatorias/{id}", {"titulo": "otro"}),
    ("patch", "/convocatorias/{id}/estado", {"estado": "programada"}),
    ("post", "/convocatorias/{id}/censo", {"identificadores": ["a"]}),
    ("post", "/convocatorias/{id}/acta", None),
    ("post", "/convocatorias/{id}/presencial/codigo", {"registrador": "admin"}),
    ("post", "/convocatorias/{id}/aval/dar", {"avalador_credencial": "a", "avalado_identificador": "b"}),
]


def _llamar(api, metodo, ruta, cuerpo, cid, headers=None):
    return api.client.request(metodo, ruta.format(id=cid), json=cuerpo, headers=headers or {})


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_ADMIN)
def test_sin_cabecera_403_antes_que_404(api, metodo, ruta, cuerpo):
    assert _llamar(api, metodo, ruta, cuerpo, "no-existe").status_code == 403  # auth antes que 404


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_ADMIN)
def test_cabecera_incorrecta_403(api, metodo, ruta, cuerpo):
    assert _llamar(api, metodo, ruta, cuerpo, "no-existe", {"X-Admin-Token": "x" * 32}).status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_ADMIN)
def test_sin_token_configurado_503(api, monkeypatch, metodo, ruta, cuerpo):
    monkeypatch.delenv("PANRAP_ADMIN_TOKEN")
    assert _llamar(api, metodo, ruta, cuerpo, "x", {"X-Admin-Token": "t" * 32}).status_code == 503


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_ADMIN)
def test_token_corto_503(api, monkeypatch, metodo, ruta, cuerpo):
    monkeypatch.setenv("PANRAP_ADMIN_TOKEN", "corto")
    assert _llamar(api, metodo, ruta, cuerpo, "x", {"X-Admin-Token": "corto"}).status_code == 503


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_ADMIN)
def test_cabecera_correcta_pasa_la_auth(api, metodo, ruta, cuerpo):
    cid = crear_conv(api, ["a"], estado="programada")
    r = _llamar(api, metodo, ruta, cuerpo, cid, api.admin)
    assert r.status_code not in (403, 503), r.text


def test_rutas_publicas_no_exigen_token(api):
    c = api.client
    assert c.get("/convocatorias/no-existe").status_code == 404
    assert c.get("/convocatorias/no-existe/escrutinio").status_code == 404
    assert c.get("/convocatorias/no-existe/urna").status_code == 404
    assert c.post("/convocatorias/no-existe/emision/inicio", json={"credencial": "a"}).status_code == 404
    assert c.post("/convocatorias/no-existe/emision/fin", json={"sesion": "a", "e": "00"}).status_code == 403
    assert c.post("/convocatorias/no-existe/votos", json={"opcion": "a", "r_prima": "00" * 33, "s_prima": "00" * 32}).status_code == 404
