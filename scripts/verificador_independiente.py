#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Verificador independiente de la urna: no necesita la BD ni ninguna clave privada.

Uso: verificador_independiente.py <conv_id> [--api URL] [--Y HEX] [--log-pub HEX] [--archivo observador.jsonl]
Comprueba: firma de cada voto, duplicados, recuento, hash de la urna y el REGISTRO (checkpoints firmados,
encadenados, con raíces Merkle recalculadas sobre los votos publicados).
Pasa --Y y --log-pub obtenidas por un canal distinto al servidor (acta, registro público): si se toman de la
propia API, un servidor deshonesto podría servir claves a medida y todo «verificaría». Con --archivo (generado por
scripts/observador.py durante la votación) se detecta además que el servidor reescriba su historia.
Códigos de salida: 0 correcto · 2 uso · 3 error HTTP · 4 sin Y · 5 clave inválida · 10 urna o registro incoherentes."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import registro  # noqa: E402
from urna_publica import urna_sha256  # noqa: E402
from urna_schnorr import verificar  # noqa: E402


def verificar_urna(data: dict, Y: bytes, conv_id: str, log_pub: bytes | None = None, archivados: list | None = None) -> dict:
    """Función pura. log_pub: clave del registro fijada por el verificador (si no, se usa la que publica la urna)."""
    votos = [(bytes.fromhex(v["r_prima"]), bytes.fromhex(v["s_prima"]), v["opcion"], v.get("lote")) for v in data.get("votos", [])]
    validos = sum(1 for r, s, op, _ in votos if verificar(Y, conv_id, op, r, s))
    duplicados = len(votos) - len({r for r, _, _, _ in votos})
    hash_ok = data.get("urna_sha256") in (None, urna_sha256([(r, s, op) for r, s, op, _ in votos]))
    reg = data.get("registro")
    problemas = []
    if not reg:
        problemas.append("la urna no incluye registro de checkpoints")
    else:
        try:
            pub = log_pub or bytes.fromhex(reg["log_pub_hex"])
            problemas += registro.verificar_registro(conv_id, pub, reg["checkpoints"], votos)
            if archivados:
                problemas += registro.comparar_con_archivo(archivados, reg["checkpoints"])
        except (KeyError, ValueError, TypeError):
            problemas.append("registro con formato inválido")
    return {"validos": validos, "invalidos": len(votos) - validos, "duplicados": duplicados,
            "total_ok": data.get("total_votos") == len(votos), "hash_ok": hash_ok, "problemas_registro": problemas}


def _obtener(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


class ClaveInvalida(ValueError):
    pass


def _hex(valor: str, nombre: str, largo: int = 33) -> bytes:
    try:
        b = bytes.fromhex(valor)
    except ValueError:
        b = b""
    if len(b) != largo:
        raise ClaveInvalida(f"{nombre} inválida (se esperan {largo} bytes en hex)")
    return b


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("conv_id")
    ap.add_argument("--api", default=os.getenv("PANRAP_API_URL", "http://localhost:8000"))
    ap.add_argument("--Y", help="clave pública de firma de la convocatoria (hex, 66 caracteres), fuera de banda")
    ap.add_argument("--log-pub", help="clave pública del registro (hex, 66 caracteres), fuera de banda")
    ap.add_argument("--archivo", help="archivo JSONL del observador con los checkpoints vistos durante la votación")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        data = _obtener(f"{args.api}/convocatorias/{args.conv_id}/urna")
    except (urllib.error.URLError, ValueError) as exc:
        print(f"ERROR: no se pudo obtener la urna: {exc}", file=sys.stderr)
        return 3
    y_hex = args.Y or data.get("emisor_pub_hex", "")
    if not y_hex:
        print("ERROR: no hay clave Y", file=sys.stderr)
        return 4
    if not args.Y:
        print("ADVERTENCIA: Y tomada del propio servidor; contrástala con el registro público/acta.", file=sys.stderr)
    if not args.log_pub:
        print("ADVERTENCIA: clave del registro tomada del propio servidor; fíjala con --log-pub.", file=sys.stderr)
    archivados = None
    if args.archivo:
        with open(args.archivo, encoding="utf-8") as f:
            archivados = [json.loads(linea) for linea in f if linea.strip() and json.loads(linea).get("tipo") != "cabecera"]
    try:
        Y, log_pub = _hex(y_hex, "Y"), (_hex(args.log_pub, "log-pub") if args.log_pub else None)
    except ClaveInvalida as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 5
    r = verificar_urna(data, Y, args.conv_id, log_pub, archivados)
    print(f"VERIFICACIÓN: {r['validos']} válidos, {r['invalidos']} inválidos, {r['duplicados']} duplicados "
          f"(conv_id={args.conv_id})")
    n_cp = len((data.get("registro") or {}).get("checkpoints", []))
    print(f"REGISTRO: {n_cp} checkpoints; {'sin problemas' if not r['problemas_registro'] else str(len(r['problemas_registro'])) + ' problemas'}")
    for p in r["problemas_registro"]:
        print(f"  - {p}", file=sys.stderr)
    if r["invalidos"] or r["duplicados"] or not r["total_ok"] or not r["hash_ok"] or r["problemas_registro"]:
        print("URNA O REGISTRO INCOHERENTES: no se puede dar por verificada.", file=sys.stderr)
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(main())
