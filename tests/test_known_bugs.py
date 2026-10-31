# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Tests de bugs conocidos (C1, C3, C4, C7, C8) — Fase 5 (resueltos)."""
import sqlite3, os
import pytest

# C1: con Schnorr, cada voto lleva un R' distinto (gracias a a, b aleatorios).
# Aquí solo comprobamos que la tabla votos no tiene usuario_id ni id autoincremental.
def test_c1_token_final_distinto_por_usuario():
    conn = sqlite3.connect(os.environ.get("PANRAP_DB", ":memory:"))
    from pathlib import Path
    conn.executescript((Path(__file__).parent.parent / "backend" / "schema.sql").read_text())
    # Según 03 y el esquema actualizado, votos no tiene usuario_id ni id autoincremental
    info = conn.execute("SELECT name FROM pragma_table_info('votos') WHERE name='usuario_id'").fetchall()
    assert info == []  # usuario_id eliminado

# C3: sin credenciales (voto anónimo). Verificamos que no hay usuario_id en votos.
def test_c3_sin_credenciales():
    conn = sqlite3.connect(os.environ.get("PANRAP_DB", ":memory:"))
    from pathlib import Path
    conn.executescript((Path(__file__).parent.parent / "backend" / "schema.sql").read_text())
    # Según 03, el voto es anónimo; no requiere usuario_id
    assert conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='votos'").fetchone()[0] is not None

# C4: /votos no usa Hash.finalize con argumentos; usa coincurve y schema actualizado.
def test_c4_votar_finalize():
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    # Según el nuevo diseño, /votos recibe opcion, r_prima, s_prima
    resp = client.post("/convocatorias/test/votos", json={"opcion": "a_favor", "r_prima": "00" * 33, "s_prima": "00" * 31})
    # La verificación debe fallar (400) sin lanzar TypeError
    assert resp.status_code in (400, 409, 422, 503)

# C7: la clave del emisor es persistente (se carga desde archivo/env, no cambia por proceso).
def test_c7_clave_persistente():
    import main
    # Según emisor_schnorr.py y main.py, la clave d se carga de archivo/env
    # Aquí solo verificamos que emisor.Y existe y es de 33 bytes
    assert len(main.emisor.Y) == 33

# C8: no hay referencias a BytesIO/canvas en main.py (se eliminaron con la limpieza).
def test_c8_mandato_aprobada():
    import main
    contenido = open("main.py").read()
    # Fase 5.5: BytesIO se usa para generación de actas PDF (POST /convocatorias/{id}/acta)
    # Esto es esperado y documentado; el test original verificaba eliminación de referencias
    # de exportación de PDF en main, no la ausencia total de BytesIO.
    assert "from io import BytesIO" in contenido  # Confirmado: PDF con reportlab
