# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""API FastAPI — Fase 5 (Blind Schnorr). Usa solo coincurve para secretos (S4)."""
import os, sqlite3, secrets
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

import re

def _validar_convocatoria_id(conv_id: str) -> bool:
    if not isinstance(conv_id, str) or len(conv_id) == 0 or len(conv_id) > 64:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', conv_id))

from elegibilidad import Padron

# Regla S4: toda aritmética con secretos pasa por coincurve (Emisor)
from emisor_schnorr import Emisor, EmisionOcupada, SesionInvalida, EntradaInvalida
import urna_schnorr

def _get_conn():
    conn = sqlite3.connect(DB_PATH())
    if DB_PATH() == ":memory:" or not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emisiones'").fetchone():
        with open("backend/schema.sql") as f:
            conn.executescript(f.read())
        conn.commit()
    return conn

app = FastAPI()
import hashlib, json

@app.post("/convocatorias", status_code=201)
async def crear_convocatoria(payload: dict):
    titulo = payload.get("titulo")
    texto = payload.get("texto")
    opciones = payload.get("opciones", ["a_favor", "en_contra", "abstencion"])
    modo = payload.get("modo_elegibilidad", "padron")
    nivel = payload.get("nivel_garantia", "media")
    if not titulo or not texto:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios: titulo, texto")
    import uuid
    conv_id = str(uuid.uuid4())
    texto_sha256 = hashlib.sha256(texto.encode()).hexdigest()
    secreto_bytes = secrets.token_bytes(32)
    emisor_pub_hex = emisor.Y.hex()
    emisor_pub_sha256 = hashlib.sha256(emisor.Y).hexdigest()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO convocatorias (id, propuesta_id, titulo, texto_sha256, opciones_json, modo_elegibilidad, nivel_garantia, estado, emisor_pub_hex, emisor_pub_sha256, secreto_hmac) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conv_id, 1, titulo, texto_sha256, json.dumps(opciones), modo, nivel, "borrador", emisor_pub_hex, emisor_pub_sha256, secreto_bytes)
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "estado": "borrador"}

DB_PATH = lambda: os.getenv("PANRAP_DB", str(Path(__file__).parent / "panrap.db"))

# Cargar clave del emisor (prioridad: env var > archivo local > efímera)
_d_bytes = None
if "PANRAP_EMISOR_KEY_HEX" in os.environ:
    _d_bytes = bytes.fromhex(os.environ["PANRAP_EMISOR_KEY_HEX"])
elif (Path(__file__).parent / "clave_emisor.hex").exists():
    _d_bytes = (Path(__file__).parent / "clave_emisor.hex").read_bytes().strip()
if _d_bytes is None:
    _d_bytes = secrets.token_bytes(32)
if len(_d_bytes) != 32:
    raise ValueError("Clave del emisor debe tener exactamente 32 bytes")

emisor = Emisor(_d_bytes)

@app.post("/convocatorias/{conv_id}/emision/inicio")
async def inicio(conv_id: str, payload: dict = {}):
    payload = payload or {}
    credencial = payload.get("credencial")
    if not credencial:
        raise HTTPException(status_code=400, detail="Falta credencial del usuario")
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    conn = _get_conn()
    row = conn.execute(
        "SELECT estado, modo_elegibilidad, secreto_hmac FROM convocatorias WHERE id = ?",
        (conv_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
    estado, modo, secreto_bytes = row
    if estado not in ("emision", "votacion"):
        conn.close()
        raise HTTPException(status_code=400, detail=f"Convocatoria no abierta (estado: {estado})")
    # Cargar censo desde BD (o vacío si no existe)
    censo_rows = conn.execute(
        "SELECT persona_ref FROM personas WHERE convocatoria_id = ?", (conv_id,)
    ).fetchall()
    censo_set = {r[0] for r in censo_rows}
    # Validar duplicados: misma persona_ref ya emitió
    proveedor = Padron(secreto_bytes, censo=censo_set)
    persona_ref = proveedor.registrar(conv_id, {"identificador": credencial})
    if persona_ref is None:
        conn.close()
        raise HTTPException(status_code=403, detail="Persona no elegible (no en censo)")
    existe = conn.execute(
        "SELECT 1 FROM emisiones WHERE convocatoria_id = ? AND persona_ref = ?",
        (conv_id, persona_ref)
    ).fetchone()
    if existe:
        conn.close()
        raise HTTPException(status_code=409, detail="Ya emitió para esta convocatoria")
    # S1: cerrojo
    try:
        sid, R = emisor.inicio()
    except EmisionOcupada:
        raise HTTPException(status_code=503, detail="Servicio ocupado; reintente en 10s", headers={"Retry-After": "10"})
    conn.execute(
        "INSERT INTO emisiones (convocatoria_id, persona_ref, estado, intentos) VALUES (?, ?, ?, ?)",
        (conv_id, persona_ref, "pendiente", 1),
    )
    conn.commit()
    conn.close()
    return {"sid": sid, "R": R.hex()}

@app.post("/convocatorias/{conv_id}/emision/fin")
async def fin(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    session_id = payload.get("sesion")
    e = bytes.fromhex(payload.get("e", "")) if isinstance(payload.get("e"), str) else payload.get("e")
    try:
        s = emisor.fin(str(session_id), bytes(e) if isinstance(e, bytes) else bytes.fromhex(str(e)) if isinstance(e, str) else b"")
    except (SesionInvalida, EntradaInvalida) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, EntradaInvalida) else 403, detail=str(exc))
    conn = _get_conn()
    conn.execute(
        "UPDATE emisiones SET estado = ? WHERE convocatoria_id = ? AND estado = ?",
        ("completada", conv_id, "pendiente"),
    )
    conn.commit()
    conn.close()
    return {"s": s.hex()}

@app.post("/convocatorias/{conv_id}/censo", status_code=201)
async def cargar_censo(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    identificadores = payload.get("identificadores", [])
    conn = _get_conn()
    row = conn.execute("SELECT secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
    secreto_bytes = row[0]
    proveedor = Padron(secreto_bytes)
    for ident in identificadores:
        persona_ref = proveedor.registrar(conv_id, {"identificador": ident})
        if persona_ref:
            conn.execute(
                "INSERT OR IGNORE INTO personas (convocatoria_id, persona_ref, alta_por) VALUES (?, ?, ?)",
                (conv_id, persona_ref, ident)
            )
    conn.commit()
    conn.close()
    return {"convocatoria_id": conv_id, "cargados": len(identificadores)}

@app.post("/convocatorias/{conv_id}/votos")
async def votar(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    opcion = payload.get("opcion")
    r_hex = payload.get("r_prima")
    s_hex = payload.get("s_prima")
    if not opcion or not r_hex or not s_hex:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios")
    r_prima = bytes.fromhex(r_hex)
    s_prima = bytes.fromhex(s_hex)
    # Verificación pública con coincurve (S4 no aplica a datos públicos, pero se usa coincurve)
    if not urna_schnorr.verificar(emisor.Y, conv_id, opcion, r_prima, s_prima):
        raise HTTPException(status_code=400, detail="Verificación fallida")
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO votos (convocatoria_id, r_prima, s_prima, opcion) VALUES (?, ?, ?, ?)",
            (conv_id, r_prima, s_prima, opcion),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Token gastado")
    conn.close()
    return {"id": r_hex}
