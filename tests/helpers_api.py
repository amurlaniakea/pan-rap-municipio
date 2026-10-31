# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Cliente Blind Schnorr de referencia y utilidades para probar la API de extremo a extremo (solo tests)."""
import secrets

from coincurve import PrivateKey, PublicKey

import urna_schnorr as U

Q = U.Q
OPCIONES = ("a_favor", "en_contra", "abstencion")


def blindar(Y: bytes, R: bytes, conv_id: str, opcion: str, a=None, b=None):
    """Devuelve (e_bytes, finalizar); finalizar(s_bytes) -> (R_prima, s_prima)."""
    a = a if a is not None else secrets.randbelow(Q - 1) + 1
    b = b if b is not None else secrets.randbelow(Q - 1) + 1
    Rp = PublicKey.combine_keys([
        PublicKey(R),
        PrivateKey(a.to_bytes(32, "big")).public_key,
        PublicKey(Y).multiply(b.to_bytes(32, "big"), update=False),
    ]).format()
    e = (U.desafio(Y, Rp, U.mensaje(conv_id, opcion)) + b) % Q

    def finalizar(s: bytes):
        return Rp, ((int.from_bytes(s, "big") + a) % Q).to_bytes(32, "big")

    return e.to_bytes(32, "big"), finalizar


def crear_conv(api, identificadores, opciones=OPCIONES, estado="emision"):
    """Crea una convocatoria, carga el censo y la lleva hasta `estado` (programada/emision/votacion)."""
    r = api.client.post("/convocatorias", headers=api.admin, json={
        "titulo": "t", "texto": "x", "opciones": list(opciones),
        "emision_abre_en": "2026-11-01T00:00:00", "voto_abre_en": "2026-11-02T00:00:00",
        "cierra_en": "2026-11-03T00:00:00"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    c = api.client.post(f"/convocatorias/{cid}/censo", headers=api.admin, json={"identificadores": list(identificadores)})
    assert c.status_code == 201, c.text
    for st in ("programada", "emision", "votacion"):
        p = api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": st})
        assert p.status_code == 200, p.text
        if st == estado:
            break
    return cid


def clave_Y(api, cid) -> bytes:
    return bytes.fromhex(api.client.get(f"/convocatorias/{cid}").json()["emisor_pub_hex"])


def emitir_token(api, cid, credencial, opcion, msg_conv=None):
    """Recorre inicio/fin como un votante. msg_conv permite firmar un mensaje de OTRA convocatoria."""
    r = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": credencial})
    assert r.status_code == 200, r.text
    d = r.json()
    e, finalizar = blindar(clave_Y(api, cid), bytes.fromhex(d["R"]), msg_conv or cid, opcion)
    f = api.client.post(f"/convocatorias/{cid}/emision/fin", json={"sesion": d["sid"], "e": e.hex()})
    assert f.status_code == 200, f.text
    return finalizar(bytes.fromhex(f.json()["s"]))


def votar(api, cid, opcion, R_prima, s_prima):
    return api.client.post(f"/convocatorias/{cid}/votos",
                           json={"opcion": opcion, "r_prima": R_prima.hex(), "s_prima": s_prima.hex()})
