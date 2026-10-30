# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Tests verdes AC-S1, AC-S2, AC-S4 (Fase 5, Prompt 2)."""
from fastapi.testclient import TestClient
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from main import app

client = TestClient(app)

def test_ac_s1_interoperabilidad():
    resp = client.post("/convocatorias/test/emision/inicio")
    assert resp.status_code == 200
    data = resp.json()
    assert len(bytes.fromhex(data["R"])) == 33

def test_ac_s2_bloqueo_concurrencia():
    resp1 = client.post("/convocatorias/test/emision/inicio")
    assert resp1.status_code == 200
    resp2 = client.post("/convocatorias/test/emision/inicio")
    assert resp2.status_code == 503

def test_ac_s4_validacion_estricta():
    resp = client.post("/convocatorias/test/emision/fin", json={"sesion": "bad", "e": "00"})
    assert resp.status_code in (400, 403, 422)
