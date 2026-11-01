#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Observador del registro: archiva los checkpoints firmados de una convocatoria mientras dura la votación.

Uso: observador.py <conv_id> [--api URL] [--log-pub HEX] [--archivo FILE.jsonl] [--cada SEGUNDOS] [--una-vez]
Ejecútalo en una máquina distinta de la del servidor (idealmente varias personas, de forma independiente) y
publica el archivo donde quieras. Si el servidor enseña a dos observadores historias distintas, las dos firmas son
una prueba transferible de equivocación. Fija --log-pub con la clave anunciada ANTES de abrir la votación.
Códigos de salida: 0 correcto · 3 error HTTP · 5 clave inválida · 20 equivocación/retroceso · 22 firma o cadena inválidas."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import registro  # noqa: E402


def _obtener(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def _cargar(archivo):
    cabecera, cps = None, []
    if archivo and os.path.exists(archivo):
        with open(archivo, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    d = json.loads(linea)
                    if d.get("tipo") == "cabecera":
                        cabecera = d
                    else:
                        cps.append(d)
    return cabecera, cps


def observar(conv_id: str, servido: dict, cabecera: dict | None, archivados: list, log_pub_fijada: str | None):
    """Función pura. Devuelve (código, cabecera, nuevos, mensajes)."""
    pub_hex = log_pub_fijada or (cabecera or {}).get("log_pub_hex") or servido.get("log_pub_hex", "")
    mensajes = []
    if cabecera and log_pub_fijada and cabecera["log_pub_hex"] != log_pub_fijada:
        return 22, cabecera, [], ["la clave fijada no coincide con la del archivo"]
    if servido.get("log_pub_hex") != pub_hex:
        return 22, cabecera, [], ["el servidor sirve una clave de registro distinta de la fijada"]
    try:
        pub = bytes.fromhex(pub_hex)
    except ValueError:
        return 5, cabecera, [], ["clave del registro inválida"]
    cps = servido["checkpoints"]
    mensajes += registro.verificar_cadena(conv_id, pub, cps)
    if mensajes:
        return 22, cabecera, [], mensajes
    conflictos = registro.comparar_con_archivo(archivados, cps)
    if conflictos:
        return 20, cabecera, [], conflictos
    nuevos = [cp for cp in cps if cp["seq"] > len(archivados)]
    return 0, cabecera or {"tipo": "cabecera", "convocatoria_id": conv_id, "log_pub_hex": pub_hex}, nuevos, []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("conv_id")
    ap.add_argument("--api", default=os.getenv("PANRAP_API_URL", "http://localhost:8000"))
    ap.add_argument("--log-pub")
    ap.add_argument("--archivo")
    ap.add_argument("--cada", type=float, default=30.0)
    ap.add_argument("--una-vez", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    archivo = args.archivo or f"observador_{args.conv_id}.jsonl"
    while True:
        try:
            servido = _obtener(f"{args.api}/convocatorias/{args.conv_id}/registro")
        except (urllib.error.URLError, ValueError) as exc:
            print(f"ERROR: no se pudo obtener el registro: {exc}", file=sys.stderr)
            return 3
        cabecera, archivados = _cargar(archivo)
        codigo, cabecera, nuevos, mensajes = observar(args.conv_id, servido, cabecera, archivados, args.log_pub)
        if codigo:
            print("ALERTA: " + "; ".join(mensajes), file=sys.stderr)
            return codigo
        archivo_nuevo = not os.path.exists(archivo) or os.path.getsize(archivo) == 0
        with open(archivo, "a", encoding="utf-8") as f:
            if archivo_nuevo:
                f.write(json.dumps(cabecera, sort_keys=True) + "\n")
            for cp in nuevos:
                f.write(json.dumps(cp, sort_keys=True) + "\n")
        print(f"OK: {len(archivados) + len(nuevos)} checkpoints archivados ({len(nuevos)} nuevos) en {archivo}")
        if args.una_vez:
            return 0
        time.sleep(args.cada)


if __name__ == "__main__":
    sys.exit(main())
