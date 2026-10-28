# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Ayudantes de los tests de Blind Schnorr: vectores públicos y cliente de referencia (solo tests).

Al importar este módulo solo se cargan módulos estándar: coincurve y los módulos de producción
se importan dentro de las funciones, para que la suite siga coleccionando sin ellos."""
import json
import pathlib

Q = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def cargar_vectores():
    ruta = pathlib.Path(__file__).parent / "vectors" / "schnorr_vectors.json"
    return json.loads(ruta.read_text())


def cliente_firma(emisor, convocatoria_id, opcion):
    """Cliente Blind Schnorr de referencia en Python (solo tests). Devuelve (R_prima 33 B, s_prima 32 B)."""
    from coincurve import PrivateKey, PublicKey

    import urna_schnorr as u

    sesion, R33 = emisor.inicio()
    a, b = PrivateKey(), PrivateKey()
    Ypk = PublicKey(emisor.Y)
    Rp33 = PublicKey.combine_keys([PublicKey(R33), a.public_key, Ypk.multiply(b.secret, update=False)]).format()
    e = (u.desafio(emisor.Y, Rp33, u.mensaje(convocatoria_id, opcion)) + int.from_bytes(b.secret, "big")) % Q
    e32 = e.to_bytes(32, "big")
    s = emisor.fin(sesion, e32)
    # el cliente comprueba la respuesta antes de aceptarla: s·G = R + e·Y
    lhs = PrivateKey(s).public_key.format()
    rhs = PublicKey.combine_keys([PublicKey(R33), Ypk.multiply(e32, update=False)]).format()
    if lhs != rhs:
        raise ValueError("respuesta del Emisor inválida")
    sp = (int.from_bytes(s, "big") + int.from_bytes(a.secret, "big")) % Q
    return Rp33, sp.to_bytes(32, "big")
