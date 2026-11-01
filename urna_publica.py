# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Huella pública de la urna con codificación inequívoca (cada voto: r(33) ‖ s(32) ‖ len(opción) ‖ opción)."""
import hashlib


def urna_sha256(votos) -> str:
    """votos: iterable de (r_prima: bytes, s_prima: bytes, opcion: str). El orden de entrada no importa."""
    h = hashlib.sha256()
    for r, s, opcion in sorted(votos, key=lambda v: bytes(v[0])):
        ob = opcion.encode()
        if len(ob) > 255:
            raise ValueError("opción demasiado larga")
        h.update(bytes(r) + bytes(s) + bytes([len(ob)]) + ob)
    return h.hexdigest()


def hoja_voto(r_prima: bytes, s_prima: bytes, opcion: str) -> bytes:
    """Contenido de la hoja del registro de un voto: r(33) ‖ s(32) ‖ len(opción) ‖ opción."""
    ob = opcion.encode()
    if len(ob) > 255:
        raise ValueError("opción demasiado larga")
    return bytes(r_prima) + bytes(s_prima) + bytes([len(ob)]) + ob
