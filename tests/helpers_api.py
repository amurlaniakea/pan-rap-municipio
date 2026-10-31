# SPDX-License-Identifier: AGPL-3.0-or-later
# Ayudante de referencia para tests de API (Blind Schnorr)
import secrets
from coincurve import PrivateKey, PublicKey
import urna_schnorr as U

Q = U.Q

def blindar(Y: bytes, R: bytes, conv_id: str, opcion: str, a: int | None = None, b: int | None = None):
    a = a if a is not None else secrets.randbelow(Q - 1) + 1
    b = b if b is not None else secrets.randbelow(Q - 1) + 1
    Rp = PublicKey.combine_keys([
        PublicKey(R),
        PrivateKey(a.to_bytes(32, "big")).public_key,
        PublicKey(Y).multiply(b.to_bytes(32, "big"), update=False)
    ]).format()
    e = (U.desafio(Y, Rp, U.mensaje(conv_id, opcion)) + b) % Q
    def finalizar(s: bytes):
        return Rp, ((int.from_bytes(s, "big") + a) % Q).to_bytes(32, "big")
    return e.to_bytes(32, "big"), finalizar

def emitir_token(client, conv_id, credencial, opcion, Y: bytes):
    r = client.post(f"/convocatorias/{conv_id}/emision/inicio", json={"credencial": credencial})
    assert r.status_code == 200, r.text
    d = r.json()
    e, fin = blindar(Y, bytes.fromhex(d["R"]), conv_id, opcion)
    f = client.post(f"/convocatorias/{conv_id}/emision/fin", json={"sesion": d["sid"], "e": e.hex()})
    assert f.status_code == 200, f.text
    return fin(bytes.fromhex(f.json()["s"]))

def votar(client, conv_id, opcion, R_prima, s_prima):
    return client.post(f"/convocatorias/{conv_id}/votos",
                       json={"opcion": opcion, "r_prima": R_prima.hex(), "s_prima": s_prima.hex()})
