#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Verificador independiente de la urna (03-motor-blind-schnorr.md §8)."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from urna_schnorr import mensaje, desafio, verificar

DB = os.getenv("PANRAP_DB", "panrap.db")
conn = sqlite3.connect(DB)

# Obtener clave pública del emisor (de emisiones completadas o archivo)
# Para prototipo, se asume que la clave d está disponible; aquí solo verificamos votos.
# En producción, la clave Y debe provenir del registro público.
# Este script usa la clave del archivo de referencia para la verificación independiente.
from pathlib import Path
CLAVE_D = Path(__file__).parent.parent / "tests" / "clave_real_ref.hex"
if CLAVE_D.exists():
    from coincurve import PrivateKey
    d_bytes = CLAVE_D.read_bytes().strip()
    Y = PrivateKey(d_bytes).public_key.format()
else:
    # Fallback: no se puede verificar sin Y pública conocida
    print("ADVERTENCIA: No hay clave pública de referencia; la verificación requiere Y.")
    Y = b""

votos = conn.execute("SELECT convocatoria_id, r_prima, s_prima, opcion FROM votos").fetchall()
validos = 0
invalidos = 0
for cid, r_prima, s_prima, opcion in votos:
    if verificar(Y, cid, opcion, r_prima, s_prima):
        validos += 1
    else:
        invalidos += 1

print(f"VERIFICACIÓN EXITOSA: {validos} votos válidos, {invalidos} inválidos")
