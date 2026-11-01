# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Clave maestra del emisor (S7) y derivación de una clave por convocatoria (Fase 6a, D7/D11).

La clave de firma de cada convocatoria se deriva de la maestra con HMAC-SHA256; así una firma
emitida para una convocatoria no es válida en otra. Solo se usa hashlib/hmac y coincurve (S4)."""
import hashlib
import hmac
import os
import secrets
import sys
from pathlib import Path

from coincurve import PrivateKey

_DEBILES = {b"\x00" * 32, (1).to_bytes(32, "big")}


def _validar(d: bytes) -> bytes:
    if len(d) != 32:
        raise RuntimeError("La clave maestra debe tener 32 bytes (64 caracteres hex)")
    if d in _DEBILES:
        raise RuntimeError("Clave maestra rechazada: es una clave de ejemplo/débil")
    try:
        PrivateKey(d)
    except ValueError as exc:
        raise RuntimeError(f"Clave maestra rechazada por libsecp256k1: {exc}") from exc
    return d


def _desde_hex(texto: str, origen: str) -> bytes:
    texto = texto.strip()
    if len(texto) != 64:
        raise RuntimeError(f"{origen} debe tener exactamente 64 caracteres hex")
    try:
        return _validar(bytes.fromhex(texto))
    except ValueError as exc:
        raise RuntimeError(f"{origen} contiene hex inválido") from exc


def cargar_clave_maestra(env=None, base_dir: Path | None = None) -> bytes:
    """env PANRAP_EMISOR_KEY_HEX > fichero (PANRAP_EMISOR_KEY_FILE o clave_emisor.hex, modo 0600).

    Sin clave: falla, salvo PANRAP_ALLOW_EPHEMERAL_KEY=1 (solo desarrollo y tests)."""
    env = os.environ if env is None else env
    base_dir = Path(__file__).parent if base_dir is None else base_dir
    if env.get("PANRAP_EMISOR_KEY_HEX", "").strip():
        return _desde_hex(env["PANRAP_EMISOR_KEY_HEX"], "PANRAP_EMISOR_KEY_HEX")
    ruta = Path(env.get("PANRAP_EMISOR_KEY_FILE") or base_dir / "clave_emisor.hex")
    if ruta.exists():
        if os.name == "posix" and (ruta.stat().st_mode & 0o077):
            raise RuntimeError(f"{ruta.name}: permisos demasiado abiertos; ejecuta chmod 600")
        return _desde_hex(ruta.read_text(), ruta.name)
    if env.get("PANRAP_ALLOW_EPHEMERAL_KEY") == "1":
        print("ADVERTENCIA: clave efímera (PANRAP_ALLOW_EPHEMERAL_KEY=1); no usar en producción.", file=sys.stderr)
        return secrets.token_bytes(32)
    raise RuntimeError(
        "No hay clave del emisor: define PANRAP_EMISOR_KEY_HEX o crea clave_emisor.hex (chmod 600)")


def _derivar(master: bytes, etiqueta: bytes, convocatoria_id: str) -> bytes:
    base = etiqueta + convocatoria_id.encode() + b"|"
    for n in range(256):
        d = hmac.new(master, base + bytes([n]), hashlib.sha256).digest()
        try:
            PrivateKey(d)
            return d
        except ValueError:
            continue
    raise RuntimeError("No se pudo derivar una clave válida")  # probabilidad ~2^-2048


def derivar_clave_convocatoria(master: bytes, convocatoria_id: str) -> bytes:
    """d_conv = HMAC-SHA256(master, "PANRAP-KEY-v1|conv|n"); n sube hasta que libsecp256k1 acepte el escalar."""
    return _derivar(master, b"PANRAP-KEY-v1|", convocatoria_id)


def derivar_clave_registro(master: bytes, convocatoria_id: str) -> bytes:
    """Clave con la que se firman los checkpoints del registro de la convocatoria (distinta de la de firma ciega)."""
    return _derivar(master, b"PANRAP-LOG-v1|", convocatoria_id)
