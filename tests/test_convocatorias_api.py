# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""T3/T5/T8: validación al crear convocatorias, GET público y modos no implementados."""
import pytest

BASE = {"titulo": "t", "texto": "x"}


def _post(api, **extra):
    return api.client.post("/convocatorias", headers=api.admin, json={**BASE, **extra})


@pytest.mark.parametrize("extra", [
    {"titulo": ""}, {"titulo": 5}, {"texto": "  "},
    {"opciones": ["solo_una"]}, {"opciones": ["a", "a"]}, {"opciones": ["a|b", "c"]}, {"opciones": "ab"},
    {"opciones": ["a"] * 2 + [str(i) for i in range(20)]}, {"opciones": [1, 2]},
    {"nivel_garantia": "máxima"}, {"modo_elegibilidad": "aval"}, {"modo_elegibilidad": "presencial"},
    {"modo_elegibilidad": "eid"}, {"modo_elegibilidad": "inventado"},
    {"emision_abre_en": "mañana"}, {"emision_abre_en": 5},
    {"emision_abre_en": "2026-11-03T00:00:00", "voto_abre_en": "2026-11-02T00:00:00", "cierra_en": "2026-11-04T00:00:00"},
])
def test_creacion_invalida_400(api, extra):
    assert _post(api, **extra).status_code == 400


def test_creacion_valida_y_get_publico(api):
    r = _post(api, opciones=["si", "no"])
    assert r.status_code == 201
    cid = r.json()["id"]
    g = api.client.get(f"/convocatorias/{cid}")
    assert g.status_code == 200
    d = g.json()
    assert set(d) == {"id", "titulo", "texto_sha256", "opciones", "modo_elegibilidad", "estado", "emisor_pub_hex",
                      "emisor_pub_sha256", "emision_abre_en", "voto_abre_en", "cierra_en", "log_pub_hex"}
    assert d["opciones"] == ["si", "no"] and len(d["emisor_pub_hex"]) == 66
    assert "secreto" not in g.text


def test_cada_convocatoria_tiene_su_propia_clave(api):
    a = _post(api).json()["id"]
    b = _post(api).json()["id"]
    ya = api.client.get(f"/convocatorias/{a}").json()["emisor_pub_hex"]
    yb = api.client.get(f"/convocatorias/{b}").json()["emisor_pub_hex"]
    assert ya != yb


def test_presencial_y_aval_devuelven_501(api):
    cid = _post(api).json()["id"]
    assert api.client.post(f"/convocatorias/{cid}/presencial/codigo", headers=api.admin, json={"registrador": "admin"}).status_code == 501
    assert api.client.post(f"/convocatorias/{cid}/aval/dar", headers=api.admin,
                           json={"avalador_credencial": "a", "avalado_identificador": "b"}).status_code == 501


def test_patch_valida_entrada(api):
    cid = _post(api).json()["id"]
    assert api.client.patch(f"/convocatorias/{cid}", headers=api.admin, json={"titulo": 7}).status_code == 400
    assert api.client.patch(f"/convocatorias/{cid}", headers=api.admin, json={"texto": None}).status_code == 400
    assert api.client.patch(f"/convocatorias/{cid}", headers=api.admin, json={"opciones": ["x"]}).status_code == 400
    assert api.client.patch(f"/convocatorias/{cid}", headers=api.admin, json={"titulo": "ok"}).status_code == 200
