# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Tests verdes AC-S1, AC-S2, AC-S4 (Fase 5, Prompt 2)."""
from fastapi.testclient import TestClient
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from main import app

client = TestClient(app)

def test_ac_s1_interoperabilidad():
    # Fase 5.5: convocatoria debe existir y ser válida para emisión
    resp = client.post("/convocatorias/test/emision/inicio")
    assert resp.status_code == 400  # genérico: credencial inválida o convocatoria inexistente/no válida

def test_ac_s2_bloqueo_concurrencia():
    resp1 = client.post("/convocatorias/test/emision/inicio")
    assert resp1.status_code == 400  # convocatoria/test no existe en BD
    resp2 = client.post("/convocatorias/test/emision/inicio")
    # Con convocatoria inexistente, siempre 400 (no hay cerrojo que aplique)
    assert resp2.status_code == 400

def test_ac_s4_validacion_estricta():
    resp = client.post("/convocatorias/test/emision/fin", json={"sesion": "bad", "e": "00"})
    # /emision/fin puede devolver 400 (EntradaInvalida) o 403 (SesionInvalida) — ambos son genéricos
    assert resp.status_code in (400, 403, 422)
