#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Verificador independiente de la urna: no necesita la BD ni ninguna clave privada.

Uso: verificador_independiente.py <conv_id> [--api URL] [--Y HEX]
Preferible pasar --Y obtenida por un canal distinto al servidor (acta, registro público): si se toma de
la propia API, un servidor deshonesto podría servir una Y a medida y todo «verificaría».
Códigos de salida: 0 correcto · 2 uso · 3 error HTTP · 4 sin Y · 5 Y inválida · 10 urna incoherente."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from urna_publica import urna_sha256  # noqa: E402
from urna_schnorr import verificar  # noqa: E402


def verificar_urna(data: dict, Y: bytes, conv_id: str) -> dict:
    """Función pura: comprueba cada firma, duplicados, el recuento declarado y el hash de la urna."""
    votos = [(bytes.fromhex(v["r_prima"]), bytes.fromhex(v["s_prima"]), v["opcion"]) for v in data.get("votos", [])]
    validos = sum(1 for r, s, op in votos if verificar(Y, conv_id, op, r, s))
    duplicados = len(votos) - len({r for r, _, _ in votos})
    hash_ok = data.get("urna_sha256") in (None, urna_sha256(votos))
    return {"validos": validos, "invalidos": len(votos) - validos, "duplicados": duplicados,
            "total_ok": data.get("total_votos") == len(votos), "hash_ok": hash_ok}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("conv_id")
    ap.add_argument("--api", default=os.getenv("PANRAP_API_URL", "http://localhost:8000"))
    ap.add_argument("--Y", help="clave pública del emisor (hex, 66 caracteres) obtenida fuera de banda")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        with urllib.request.urlopen(f"{args.api}/convocatorias/{args.conv_id}/urna", timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, ValueError) as exc:
        print(f"ERROR: no se pudo obtener la urna: {exc}", file=sys.stderr)
        return 3
    y_hex = args.Y or data.get("emisor_pub_hex", "")
    if not y_hex:
        print("ERROR: no hay clave Y", file=sys.stderr)
        return 4
    if not args.Y:
        print("ADVERTENCIA: Y tomada del propio servidor; contrástala con el registro público/acta.", file=sys.stderr)
    try:
        Y = bytes.fromhex(y_hex)
        if len(Y) != 33:
            raise ValueError
    except ValueError:
        print("ERROR: Y inválida (se esperan 33 bytes en hex)", file=sys.stderr)
        return 5
    r = verificar_urna(data, Y, args.conv_id)
    print(f"VERIFICACIÓN: {r['validos']} válidos, {r['invalidos']} inválidos, {r['duplicados']} duplicados "
          f"(conv_id={args.conv_id})")
    if r["invalidos"] or r["duplicados"] or not r["total_ok"] or not r["hash_ok"]:
        print("URNA INCOHERENTE: no se puede dar por verificada.", file=sys.stderr)
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(main())
