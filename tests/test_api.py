# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# Tests de integración con firma ECC real
from fastapi.testclient import TestClient
from main import app
import sqlite3, os, pytest

client = TestClient(app, raise_server_exceptions=False)

def test_health(monkeypatch):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["capacity_profile"] == "26k"

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C4: /votar devuelve 500 por Hash.finalize mal usado")
def test_votar_exitoso():
    payload = {"usuario_id": 1, "propuesta_id": 2, "opcion": "a_favor", "firma_ec": "a" * 64}
    r = client.post("/votar", json=payload)
    assert r.status_code in (201, 400)

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C5: UNIQUE requiere usuario_id; anónimo viola NOT NULL")
def test_doble_voto_rechazado():
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    conn.execute("DELETE FROM votos WHERE usuario_id = 1 AND propuesta_id = 2")
    conn.execute("INSERT INTO votos (propuesta_id, usuario_id, opcion, firma_ec) VALUES (?, ?, ?, ?)",
                 (2, 1, "a_favor", "b" * 64))
    conn.commit()
    conn.close()
    payload = {"usuario_id": 1, "propuesta_id": 2, "opcion": "a_favor", "firma_ec": "b" * 64}
    r = client.post("/votar", json=payload)
    assert r.status_code in (409, 400)

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C4: Hash.finalize lanza TypeError; /votar siempre 500")
def test_votar_con_firma_real_exitoso():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    private_key = ec.generate_private_key(ec.SECP256K1())
    public_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).hex()
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    conn.execute("UPDATE usuarios SET public_key = ? WHERE id = 1", (public_key_der,))
    conn.commit()
    conn.close()
    payload_str = "1:2:a_favor"
    signature_der = private_key.sign(payload_str.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    firma_hex = signature_der.hex()
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    conn.execute("DELETE FROM votos WHERE propuesta_id = 2")
    conn.commit()
    conn.close()
    payload_api = {"usuario_id": 1, "propuesta_id": 2, "opcion": "a_favor", "firma_ec": firma_hex}
    r = client.post("/votar", json=payload_api)
    assert r.status_code == 201
    assert "verificado" in r.json()["mensaje"]

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C4: payload alterado debe fallar; endpoint roto")
def test_votar_con_firma_alterada_rechazado():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    private_key = ec.generate_private_key(ec.SECP256K1())
    public_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).hex()
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    conn.execute("UPDATE usuarios SET public_key = ? WHERE id = 1", (public_key_der,))
    conn.commit()
    conn.close()
    payload_str = "1:2:en_contra"
    signature_der = private_key.sign(payload_str.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    firma_hex = signature_der.hex()
    payload_api = {"usuario_id": 1, "propuesta_id": 2, "opcion": "a_favor", "firma_ec": firma_hex}
    r = client.post("/votar", json=payload_api)
    assert r.status_code == 400
    assert "inválida" in r.json().get("detail", "").lower()

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C4: /votar 500 por TypeError; test_firma_invalida afectado")
def test_firma_invalida():
    payload = {"usuario_id": 3, "propuesta_id": 2, "opcion": "a_favor", "firma_ec": "corto"}
    r = client.post("/votar", json=payload)
    assert r.status_code == 400

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BUG-C8: ejecutar-mandato 500 por BytesIO/canvas sin importar")
def test_ejecutar_mandato_exitoso():
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    conn.execute("DELETE FROM votos WHERE propuesta_id = 2")
    conn.execute("INSERT INTO votos (propuesta_id, usuario_id, opcion, firma_ec) VALUES (?, ?, ?, ?)",
                 (2, 2, "a_favor", "b" * 64))
    conn.execute("UPDATE propuestas SET estado = 'aprobada' WHERE id = 2")
    conn.commit()
    conn.close()
    r = client.post("/propuestas/2/ejecutar-mandato")
    assert r.status_code == 202
    data = r.json()
    assert "Mandato generado" in data["mensaje"]
    assert data.get("votantes_notificados", 0) >= 1
    conn = sqlite3.connect(os.getenv("PANRAP_DB"))
    mandatos = conn.execute("SELECT * FROM mandatos WHERE propuesta_id = 2").fetchall()
    conn.close()
    assert len(mandatos) >= 1

def test_ejecutar_mandato_rechazado():
    r = client.post("/propuestas/1/ejecutar-mandato")
    assert r.status_code == 400

def test_ejecutar_mandato_duplicado():
    r = client.post("/propuestas/2/ejecutar-mandato")
    assert r.status_code in (400, 409, 202)
