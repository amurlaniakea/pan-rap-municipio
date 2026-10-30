# SPDX-License-Identifier: AGPL-3.0-or-later
from fastapi.testclient import TestClient
import sqlite3, main

def _crear_convocatoria():
    client = TestClient(main.app)
    resp = client.post("/convocatorias", json={
        "titulo": "Test",
        "texto": "Texto prueba",
        "opciones": ["a_favor", "en_contra", "abstencion"],
        "emision_abre_en": "2026-11-01T00:00:00",
        "voto_abre_en": "2026-11-02T00:00:00",
        "cierra_en": "2026-11-03T00:00:00"
    })
    assert resp.status_code == 201
    return resp.json()["id"]

def test_transicion_valida():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    resp = client.patch(f"/convocatorias/{conv_id}/estado", json={"estado": "programada"})
    assert resp.status_code == 200
    assert resp.json()["estado_nuevo"] == "programada"

def test_transicion_invalida():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    resp = client.patch(f"/convocatorias/{conv_id}/estado", json={"estado": "emision"})
    assert resp.status_code == 400

def test_actualizar_en_borrador():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    resp = client.patch(f"/convocatorias/{conv_id}", json={"titulo": "Nuevo"})
    assert resp.status_code == 200

def test_no_actualizar_en_emision():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    client.patch(f"/convocatorias/{conv_id}/estado", json={"estado": "programada"})
    client.patch(f"/convocatorias/{conv_id}/estado", json={"estado": "emision"})
    resp = client.patch(f"/convocatorias/{conv_id}", json={"titulo": "No permitido"})
    assert resp.status_code == 400

def test_destruccion_secreto_archivada():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    for est in ["programada", "emision", "votacion", "cerrada", "escrutada", "archivada"]:
        resp = client.patch(f"/convocatorias/{conv_id}/estado", json={"estado": est})
        assert resp.status_code == 200, f"Fallo en transición a {est}: {resp.text}"
    conn = sqlite3.connect(main.DB_PATH())
    row = conn.execute("SELECT secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    assert row[0] == b'\x00' or row[0] == b'\x00' * 32 or len(row[0]) == 0

def test_escrutinio_solo_cerrada():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    resp = client.get(f"/convocatorias/{conv_id}/escrutinio")
    assert resp.status_code == 400

def test_acta_solo_escrutada():
    client = TestClient(main.app)
    conv_id = _crear_convocatoria()
    resp = client.post(f"/convocatorias/{conv_id}/acta")
    assert resp.status_code == 400
