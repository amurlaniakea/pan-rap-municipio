# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Recorrido completo por la API: crear → censo → emisión → voto → cierre → escrutinio → verificador → acta."""
import importlib.util
from pathlib import Path

from helpers_api import clave_Y, crear_conv, emitir_token, votar

RAIZ = Path(__file__).parent.parent


def _verificador():
    spec = importlib.util.spec_from_file_location("verificador", RAIZ / "scripts" / "verificador_independiente.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_votacion_completa(api):
    cid = crear_conv(api, ["ana", "beto", "carla", "dani"])
    tokens = {n: emitir_token(api, cid, n, op) for n, op in
              [("ana", "a_favor"), ("beto", "a_favor"), ("carla", "en_contra")]}
    # quien ya emitió no puede emitir otra vez; quien no está en el censo, tampoco
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "ana"}).status_code == 400
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "intruso"}).status_code == 400
    # votos válidos y doble gasto
    for nombre, op in (("ana", "a_favor"), ("beto", "a_favor"), ("carla", "en_contra")):
        assert votar(api, cid, op, *tokens[nombre]).status_code == 200
    assert votar(api, cid, "a_favor", *tokens["ana"]).status_code == 409
    # el escrutinio no está disponible hasta cerrar
    assert api.client.get(f"/convocatorias/{cid}/escrutinio").status_code == 400
    assert api.client.get(f"/convocatorias/{cid}/urna").status_code == 400
    assert api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": "cerrada"}).status_code == 200
    esc = api.client.get(f"/convocatorias/{cid}/escrutinio").json()
    assert esc["recuento"] == {"a_favor": 2, "en_contra": 1, "abstencion": 0}
    assert esc["total_votos"] == 3 and esc["emisiones_completadas"] == 3 and esc["personas_en_censo"] == 4
    # urna pública + verificador con la Y publicada fuera de banda
    urna = api.client.get(f"/convocatorias/{cid}/urna").json()
    ver = _verificador()
    r = ver.verificar_urna(urna, clave_Y(api, cid), cid)
    assert r == {"validos": 3, "invalidos": 0, "duplicados": 0, "total_ok": True, "hash_ok": True, "problemas_registro": []}
    assert urna["urna_sha256"] == esc["urna_sha256"]
    # el verificador detecta manipulación
    urna["votos"][0]["opcion"] = "abstencion"
    assert ver.verificar_urna(urna, clave_Y(api, cid), cid)["invalidos"] == 1
    urna["votos"][0]["opcion"] = "a_favor"
    assert ver.verificar_urna(urna, clave_Y(api, cid), "otra-convocatoria")["validos"] == 0
    # acta
    assert api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": "escrutada"}).status_code == 200
    acta = api.client.post(f"/convocatorias/{cid}/acta", headers=api.admin)
    assert acta.status_code == 200 and acta.headers["content-type"] == "application/pdf"
