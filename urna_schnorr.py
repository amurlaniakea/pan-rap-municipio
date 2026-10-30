# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Urna Blind Schnorr (secp256k1): formato del mensaje, desafío y verificación pública.

Ver 03-motor-blind-schnorr.md §3. Este módulo solo maneja datos PÚBLICOS (clave Y, R', s', opción),
así que no hay secretos que proteger del tiempo de ejecución. Es fail-closed (K5): `verificar`
nunca lanza; cualquier entrada rara es simplemente una firma inválida.
"""
import hashlib

from coincurve import PrivateKey, PublicKey

Q = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # orden de secp256k1
_T = hashlib.sha256(b"PANRAP-BSCHNORR-v1").digest()


def mensaje(convocatoria_id: str, opcion: str) -> bytes:
    """b"PANRAP-v1|<convocatoria>|<opcion>". Rechaza campos vacíos, no textuales o con '|' (ambigüedad)."""
    for campo in (convocatoria_id, opcion):
        if not isinstance(campo, str) or not campo or "|" in campo:
            raise ValueError("campo vacío, no textual o con el separador '|'")
    return b"PANRAP-v1|" + convocatoria_id.encode("utf-8") + b"|" + opcion.encode("utf-8")


def desafio(Y: bytes, R_prima: bytes, m: bytes) -> int:
    """SHA-256(T ‖ T ‖ R' ‖ Y ‖ m) mod q, con T = SHA-256("PANRAP-BSCHNORR-v1"). Incluye la clave Y."""
    return int.from_bytes(hashlib.sha256(_T + _T + R_prima + Y + m).digest(), "big") % Q


def verificar(Y, convocatoria_id, opcion, R_prima, s_prima) -> bool:
    """True si s'·G == R' + desafio·Y para el mensaje de (convocatoria, opción)."""
    try:
        if not all(isinstance(x, bytes) for x in (Y, R_prima, s_prima)):
            return False
        if len(Y) != 33 or len(R_prima) != 33 or len(s_prima) != 32:
            return False
        e = desafio(Y, R_prima, mensaje(convocatoria_id, opcion))
        if e == 0:
            return False
        izquierda = PrivateKey(s_prima).public_key.format()  # s'·G (ValueError si s' = 0 o >= q)
        derecha = PublicKey.combine_keys(
            [PublicKey(R_prima), PublicKey(Y).multiply(e.to_bytes(32, "big"), update=False)]
        ).format()
        return izquierda == derecha
    except Exception:  # noqa: BLE001 - fail-closed: cualquier fallo es una firma inválida
        return False
