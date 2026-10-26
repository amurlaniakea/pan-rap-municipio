# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
import hashlib, math, os, secrets, sqlite3, subprocess, sys
import pytest
from fastapi.testclient import TestClient
import main

strict = TestClient(main.app)                                # propaga excepciones del servidor
loose  = TestClient(main.app, raise_server_exceptions=False) # devuelve 500
E = 65537

def _token_final(uid, pid, opcion):
    """Cliente RSA ciego: hash, cegado con r aleatorio, firma del servidor, descegado."""
    n = main.VALIDATOR_N
    m = int.from_bytes(hashlib.sha256(f"{pid}:{opcion}".encode()).digest(), "big")
    while True:
        r = secrets.randbelow(n - 2) + 2
        if math.gcd(r, n) == 1: break
    resp = loose.post("/validar-identidad", json={"usuario_id": uid, "m_blind": str((m * pow(r, E, n)) % n)})
    assert resp.status_code == 200
    return (int(resp.json()["s_blind"]) * pow(r, -1, n)) % n

@pytest.mark.xfail(strict=True, raises=TypeError, reason="BUG-C4: Hash.finalize(m) en /votar lanza TypeError")
def test_c4_votar_finalize():
    strict.post("/votar", json={"propuesta_id": 2, "opcion": "a_favor", "s_final": "123"})

@pytest.mark.xfail(strict=True, raises=sqlite3.IntegrityError, reason="BUG-C4: votos.usuario_id NOT NULL impide el voto anonimo")
def test_c4_insert_anonimo_directo():
    c = sqlite3.connect(os.environ["PANRAP_DB"])
    try:
        c.execute("INSERT INTO votos (propuesta_id, opcion, firma_ec) VALUES (2, 'a_favor', 'x')")
        c.commit()
    finally:
        c.close()

@pytest.mark.xfail(strict=True, raises=NameError, reason="BUG-C8: ejecutar-mandato usa BytesIO/canvas sin importar")
def test_c8_mandato_aprobada():
    c = sqlite3.connect(os.environ["PANRAP_DB"])
    c.execute("UPDATE propuestas SET estado='aprobada' WHERE id=2")
    c.execute("INSERT INTO votos (propuesta_id, usuario_id, opcion, firma_ec) VALUES (2, 2, 'a_favor', 'b')")
    c.commit(); c.close()
    strict.post("/propuestas/2/ejecutar-mandato")

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C1: el token final (descegado) es identico para dos usuarios con el mismo (pid, opcion)")
def test_c1_token_final_distinto_por_usuario():
    assert _token_final(1, 2, "a_favor") != _token_final(3, 2, "a_favor")

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C3: /validar-identidad responde 200 sin credenciales")
def test_c3_sin_credenciales():
    r = loose.post("/validar-identidad", json={"usuario_id": 2, "m_blind": "20"})
    assert r.status_code in (401, 403)

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C3: m_blind no numerico da 500 y quema la firma del usuario (409 despues)")
def test_c3_m_blind_no_numerico_quema_usuario():
    bad = loose.post("/validar-identidad", json={"usuario_id": 2, "m_blind": "no_num"})
    assert 400 <= bad.status_code < 500
    assert loose.post("/validar-identidad", json={"usuario_id": 2, "m_blind": "20"}).status_code == 200

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C7: la clave del validador cambia en cada proceso")
def test_c7_clave_persistente():
    cmd = [sys.executable, "-c", "import main; print(main.VALIDATOR_N)"]
    cwd = os.path.dirname(main.__file__)
    a = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout
    b = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout
    assert a.strip() and b.strip()
    assert a == b
