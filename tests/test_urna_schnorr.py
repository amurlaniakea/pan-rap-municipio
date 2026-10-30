# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Fase 2 (T-2): contrato de la Urna y de la verificación Blind Schnorr (03-motor-blind-schnorr.md:
AC-S1, AC-S5, AC-S9).

Estado: implementado en `urna_schnorr.py` (Fase 4) y `emisor_schnorr.py` (Fase 3); estos tests ya son normales.

Contrato esperado de urna_schnorr.py:
    mensaje(convocatoria_id: str, opcion: str) -> bytes
        b"PANRAP-v1|" + convocatoria_id + b"|" + opcion (UTF-8). ValueError si alguno está vacío
        o contiene "|" (evita mensajes ambiguos).
    desafio(Y: bytes, R_prima: bytes, m: bytes) -> int
        SHA-256(T ‖ T ‖ R' ‖ Y ‖ m) mod q, con T = SHA-256(b"PANRAP-BSCHNORR-v1").
    verificar(Y, convocatoria_id, opcion, R_prima, s_prima) -> bool
        s'·G == R' + desafio·Y. NUNCA lanza: cualquier entrada inválida devuelve False (K5).

Los vectores de tests/vectors/schnorr_vectors.json los generó un cliente independiente
(@noble/curves, JavaScript) contra un Emisor coincurve: la verificación se contrasta con otra
implementación y no solo consigo misma. Contienen solo datos públicos."""
import secrets

import pytest
from helpers_schnorr import Q, cargar_vectores, cliente_firma

V = cargar_vectores()
Y = bytes.fromhex(V["Y"])
CONV = V["convocatoria_id"]
TOK = V["tokens"]
OPCIONES = ("a_favor", "en_contra", "abstencion")
G33 = bytes.fromhex("0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798")
R0 = bytes.fromhex(TOK[0]["Rp"])
S0 = bytes.fromhex(TOK[0]["sp"])
O0 = TOK[0]["opcion"]


def _urna():
    import urna_schnorr as u  # importación diferida: sin módulo, falla solo este test

    return u


# ------------------------------------------------------------ AC-S1: verificación contra vectores
def test_s1_vectores_de_noble_verifican():
    u = _urna()
    assert len(TOK) == 30
    for t in TOK:
        assert u.verificar(Y, CONV, t["opcion"], bytes.fromhex(t["Rp"]), bytes.fromhex(t["sp"])) is True


MUTACIONES = {
    "opcion": lambda y, c, o, r, s: (y, c, "en_contra" if o != "en_contra" else "a_favor", r, s),
    "convocatoria": lambda y, c, o, r, s: (y, c[:-1] + "2", o, r, s),
    "R_prima": lambda y, c, o, r, s: (y, c, o, r[:-1] + bytes([r[-1] ^ 1]), s),
    "s_prima": lambda y, c, o, r, s: (y, c, o, r, s[:-1] + bytes([s[-1] ^ 1])),
    "otra_Y": lambda y, c, o, r, s: (G33, c, o, r, s),
}


@pytest.mark.parametrize("nombre", list(MUTACIONES))
def test_s1_una_mutacion_invalida_la_firma(nombre):
    u = _urna()
    for t in TOK[:10]:
        base = (Y, CONV, t["opcion"], bytes.fromhex(t["Rp"]), bytes.fromhex(t["sp"]))
        assert u.verificar(*base) is True  # control: sin mutar es válida
        assert u.verificar(*MUTACIONES[nombre](*base)) is False


MALFORMADAS = {
    "Y_vacia": (b"", CONV, O0, R0, S0),
    "Y_32_bytes": (Y[:32], CONV, O0, R0, S0),
    "Y_34_bytes": (Y + b"\x00", CONV, O0, R0, S0),
    "Y_no_es_punto": (b"\x02" + b"\xff" * 32, CONV, O0, R0, S0),
    "R_vacio": (Y, CONV, O0, b"", S0),
    "R_32_bytes": (Y, CONV, O0, R0[:32], S0),
    "R_no_es_punto": (Y, CONV, O0, b"\x02" + b"\xff" * 32, S0),
    "R_ceros": (Y, CONV, O0, b"\x00" * 33, S0),
    "s_vacio": (Y, CONV, O0, R0, b""),
    "s_31_bytes": (Y, CONV, O0, R0, S0[:31]),
    "s_cero": (Y, CONV, O0, R0, (0).to_bytes(32, "big")),
    "s_igual_a_q": (Y, CONV, O0, R0, Q.to_bytes(32, "big")),
    "s_mayor_que_q": (Y, CONV, O0, R0, b"\xff" * 32),
    "opcion_vacia": (Y, CONV, "", R0, S0),
    "convocatoria_vacia": (Y, "", O0, R0, S0),
    "separador_en_opcion": (Y, CONV, "a|b", R0, S0),
    "separador_en_convocatoria": (Y, "x|y", O0, R0, S0),
    "tipos_incorrectos": (None, None, None, None, None),
}


@pytest.mark.parametrize("nombre", list(MALFORMADAS))
def test_s1_entrada_malformada_devuelve_false_sin_lanzar(nombre):
    u = _urna()
    assert u.verificar(*MALFORMADAS[nombre]) is False


def test_s1_formato_del_mensaje():
    u = _urna()
    assert u.mensaje("conv-1", "a_favor") == b"PANRAP-v1|conv-1|a_favor"


@pytest.mark.parametrize("conv,op", [("a|b", "c"), ("a", "b|c"), ("", "x"), ("x", "")])
def test_s1_mensaje_rechaza_separadores_y_vacios(conv, op):
    u = _urna()
    with pytest.raises(ValueError):
        u.mensaje(conv, op)


def test_s1_ida_y_vuelta_emisor_cliente_urna():
    import emisor_schnorr as e
    import urna_schnorr as u

    em = e.Emisor(secrets.token_bytes(32))
    vistos = set()
    for i in range(50):
        op = OPCIONES[i % 3]
        Rp, sp = cliente_firma(em, "conv-test", op)
        assert u.verificar(em.Y, "conv-test", op, Rp, sp) is True
        vistos.add(Rp)
    assert len(vistos) == 50  # cada voto lleva un R' distinto


# ------------------------------------------------------------ AC-S9: la opción va dentro de la firma
@pytest.mark.parametrize("op_real", OPCIONES)
def test_s9_el_voto_solo_vale_para_la_opcion_firmada(op_real):
    u = _urna()
    propios = [t for t in TOK if t["opcion"] == op_real]
    assert propios
    for t in propios:
        R, s = bytes.fromhex(t["Rp"]), bytes.fromhex(t["sp"])
        assert u.verificar(Y, CONV, op_real, R, s) is True
        for otra in set(OPCIONES) - {op_real}:
            assert u.verificar(Y, CONV, otra, R, s) is False


# ------------------------------------------------------------ AC-S5: ceguera
def test_s5_toda_transcripcion_es_compatible_con_todo_voto():
    """Para cada transcripción del Emisor (R, e, s) y cada voto publicado (R', s') existe un par
    (alfa, beta) con R' = R + alfa·G + beta·Y: el Emisor no puede enlazar petición y voto."""
    u = _urna()
    from coincurve import PrivateKey, PublicKey

    Ypk = PublicKey(Y)
    for i in TOK:
        for j in TOK:
            ep = u.desafio(Y, bytes.fromhex(j["Rp"]), u.mensaje(CONV, j["opcion"]))
            alfa = (int(j["sp"], 16) - int(i["s"], 16)) % Q
            beta = (int(i["e"], 16) - ep) % Q
            lhs = PublicKey.combine_keys(
                [
                    PublicKey(bytes.fromhex(i["R"])),
                    PrivateKey(alfa.to_bytes(32, "big")).public_key,
                    Ypk.multiply(beta.to_bytes(32, "big"), update=False),
                ]
            ).format()
            assert lhs == bytes.fromhex(j["Rp"])
