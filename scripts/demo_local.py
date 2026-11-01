#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Crea una convocatoria de demostración lista para votar y muestra la URL y las credenciales.

Requiere el servidor en marcha y PANRAP_ADMIN_TOKEN en el entorno (el mismo con el que arrancó).
Solo para pruebas locales: las credenciales son identificadores en claro (votante1, votante2…)."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _llamar(api, token, metodo, ruta, cuerpo=None):
    req = urllib.request.Request(api + ruta, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Content-Type": "application/json", "X-Admin-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR {e.code} en {metodo} {ruta}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: no se pudo conectar con {api} ({e.reason}). ¿Está el servidor en marcha?")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=os.getenv("PANRAP_API_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--votantes", type=int, default=3)
    args = ap.parse_args(argv)
    token = os.getenv("PANRAP_ADMIN_TOKEN", "")
    if len(token) < 32:
        sys.exit("ERROR: exporta PANRAP_ADMIN_TOKEN (el mismo con el que arrancó el servidor).")
    cid = _llamar(args.api, token, "POST", "/convocatorias", {
        "titulo": "Demo: ¿aprobamos el presupuesto participativo?", "texto": "Convocatoria de demostración.",
        "opciones": ["a_favor", "en_contra", "abstencion"], "emision_abre_en": "2026-11-01T00:00:00",
        "voto_abre_en": "2026-11-02T00:00:00", "cierra_en": "2026-11-03T00:00:00"})["id"]
    creds = [f"votante{i}" for i in range(1, args.votantes + 1)]
    _llamar(args.api, token, "POST", f"/convocatorias/{cid}/censo", {"identificadores": creds})
    for estado in ("programada", "emision"):
        _llamar(args.api, token, "PATCH", f"/convocatorias/{cid}/estado", {"estado": estado})
    log_pub = _llamar(args.api, token, "GET", f"/convocatorias/{cid}")["log_pub_hex"]
    print(f"Convocatoria lista: {cid}")
    print(f"  Abre en el navegador: {args.api}/ui/   (o directamente {args.api}/ui/?conv={cid})")
    print(f"  Credenciales para votar: {', '.join(creds)}  (una sola vez cada una)")
    print(f"  Observador (otra terminal, durante la votación): python scripts/observador.py {cid} --api {args.api} --log-pub {log_pub} --cada 10")
    print(f"  Para cerrar y ver el recuento: PATCH {args.api}/convocatorias/{cid}/estado con {{\"estado\":\"cerrada\"}}, "
          f"luego GET {args.api}/convocatorias/{cid}/escrutinio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
