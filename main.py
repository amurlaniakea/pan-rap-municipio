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

@app.patch("/convocatorias/{conv_id}/estado")
async def cambiar_estado(conv_id: str, payload: dict = {}):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    nuevo_estado = payload.get("estado")
    estados_validos = ["borrador", "programada", "emision", "votacion", "cerrada", "escrutada", "archivada"]
    if nuevo_estado not in estados_validos:
        raise HTTPException(400, f"Estado inválido. Válidos: {estados_validos}")
    conn = _get_conn()
    row = conn.execute("SELECT estado FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    estado_actual = row[0]
    transiciones_validas = {
        "borrador": ["programada"],
        "programada": ["emision"],
        "emision": ["votacion", "cerrada"],
        "votacion": ["cerrada"],
        "cerrada": ["escrutada"],
        "escrutada": ["archivada"],
    }
    if nuevo_estado not in transiciones_validas.get(estado_actual, []):
        conn.close()
        raise HTTPException(400, f"Transición no permitida: {estado_actual} → {nuevo_estado}")
    if estado_actual == "borrador" and nuevo_estado == "programada":
        check = conn.execute("SELECT titulo, texto_sha256, opciones_json, emision_abre_en, voto_abre_en FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not all(check):
            conn.close()
            raise HTTPException(400, "Faltan campos obligatorios para programar")
    if nuevo_estado == "archivada":
        conn.execute("UPDATE convocatorias SET secreto_hmac = X'00' WHERE id = ?", (conv_id,))
    conn.execute("UPDATE convocatorias SET estado = ? WHERE id = ?", (nuevo_estado, conv_id))
    conn.commit()
    conn.close()
    return {"id": conv_id, "estado_anterior": estado_actual, "estado_nuevo": nuevo_estado}

@app.patch("/convocatorias/{conv_id}")
async def actualizar_convocatoria(conv_id: str, payload: dict = {}):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    conn = _get_conn()
    row = conn.execute("SELECT estado FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    if row[0] != "borrador":
        conn.close()
        raise HTTPException(400, "Solo se puede editar en estado borrador")
    updates = []
    values = []
    if "titulo" in payload:
        updates.append("titulo = ?")
        values.append(payload["titulo"])
    if "texto" in payload:
        updates.append("texto_sha256 = ?")
        values.append(hashlib.sha256(payload["texto"].encode()).hexdigest())
    if "opciones" in payload:
        updates.append("opciones_json = ?")
        values.append(json.dumps(payload["opciones"]))
    if "emision_abre_en" in payload:
        updates.append("emision_abre_en = ?")
        values.append(payload["emision_abre_en"])
    if "voto_abre_en" in payload:
        updates.append("voto_abre_en = ?")
        values.append(payload["voto_abre_en"])
    if "cierra_en" in payload:
        updates.append("cierra_en = ?")
        values.append(payload["cierra_en"])
    if not updates:
        conn.close()
        raise HTTPException(400, "No hay campos para actualizar")
    values.append(conv_id)
    conn.execute(f"UPDATE convocatorias SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return {"id": conv_id, "actualizado": True}

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

from io import BytesIO
from fastapi.responses import StreamingResponse

@app.post("/convocatorias/{conv_id}/acta")
async def generar_acta(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    conn = _get_conn()
    row = conn.execute(
        "SELECT estado, titulo, opciones_json, emisor_pub_hex, emisor_pub_sha256 FROM convocatorias WHERE id = ?",
        (conv_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    estado, titulo, opciones_json, emisor_pub_hex, emisor_pub_sha256 = row
    if estado != "escrutada":
        conn.close()
        raise HTTPException(400, f"Acta solo para convocatorias escrutadas (estado: {estado})")
    opciones = json.loads(opciones_json)
    recuento = {}
    for opcion in opciones:
        count = conn.execute("SELECT COUNT(*) FROM votos WHERE convocatoria_id = ? AND opcion = ?", (conv_id, opcion)).fetchone()[0]
        recuento[opcion] = count
    total_votos = sum(recuento.values())
    emisiones_completadas = conn.execute("SELECT COUNT(*) FROM emisiones WHERE convocatoria_id = ? AND estado = 'completada'", (conv_id,)).fetchone()[0]
    personas_censo = conn.execute("SELECT COUNT(*) FROM personas WHERE convocatoria_id = ?", (conv_id,)).fetchone()[0]
    votos = conn.execute("SELECT r_prima, s_prima, opcion FROM votos WHERE convocatoria_id = ? ORDER BY r_prima", (conv_id,)).fetchall()
    urna_data = b""
    for r_prima, s_prima, opcion in votos:
        urna_data += r_prima + s_prima + opcion.encode()
    urna_sha256 = hashlib.sha256(urna_data).hexdigest()
    conn.close()
    # Generación del PDF con reportlab
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width / 2, height - 50, "ACTA DE ESCRUTINIO")
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, height - 75, "PAN-RAP Municipio")
        c.setFont("Helvetica-Bold", 12)
        y_pos = height - 120
        c.drawString(50, y_pos, f"Convocatoria: {titulo}")
        y_pos -= 20
        c.drawString(50, y_pos, f"ID: {conv_id}")
        y_pos -= 20
        c.drawString(50, y_pos, f"Estado: {estado}")
        y_pos -= 40
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_pos, "RESULTADO")
        y_pos -= 30
        c.setFont("Helvetica", 12)
        for opcion, count in recuento.items():
            c.drawString(70, y_pos, f"{opcion}: {count} votos")
            y_pos -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(70, y_pos - 10, f"Total: {total_votos} votos")
        y_pos -= 30
        c.drawString(70, y_pos - 10, f"Participación: {(total_votos / personas_censo * 100) if personas_censo > 0 else 0:.1f}%")
        y_pos -= 30
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_pos, "VERIFICACIÓN")
        y_pos -= 30
        c.setFont("Helvetica", 10)
        c.drawString(50, y_pos, f"Urna SHA-256: {urna_sha256}")
        y_pos -= 15
        c.drawString(50, y_pos, f"Emisor SHA-256: {emisor_pub_sha256}")
        y_pos -= 30
        c.setFont("Helvetica", 8)
        c.drawString(50, 50, "PAN-RAP — Tecnosfera Al Servicio De La Biosfera")
        c.drawString(50, 35, "Documento generado por sistema de votación anónima.")
        c.save()
        buffer.seek(0)
    except Exception as exc:
        conn.close()
        raise HTTPException(500, f"Error generando PDF: {str(exc)}")
    conn.close()
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=acta_{conv_id}.pdf"})

@app.post("/convocatorias/{conv_id}/presencial/codigo", status_code=201)
async def generar_codigo_presencial(conv_id: str, payload: dict):
    registrador = payload.get("registrador")
    if not registrador:
        raise HTTPException(400, "Falta registrador")
    conn = _get_conn()
    row = conn.execute("SELECT secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    secreto_bytes = row[0]
    from elegibilidad import Presencial
    proveedor = Presencial(secreto_bytes)
    codigo = proveedor.generar_codigo(registrador)
    conn.close()
    if not codigo:
        raise HTTPException(403, "Registrador no autorizado")
    return {"codigo": codigo}

@app.post("/convocatorias/{conv_id}/aval/dar", status_code=201)
async def dar_aval(conv_id: str, payload: dict):
    avalador_credencial = payload.get("avalador_credencial")
    avalado_ident = payload.get("avalado_identificador")
    if not avalador_credencial or not avalado_ident:
        raise HTTPException(400, "Faltan campos")
    conn = _get_conn()
    row = conn.execute("SELECT secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    secreto_bytes = row[0]
    from elegibilidad import Aval
    proveedor = Aval(secreto_bytes)
    mensaje_avalador = f"{conv_id}:{avalador_credencial}".encode()
    import hmac, hashlib
    avalador_ref = hmac.new(secreto_bytes, mensaje_avalador, hashlib.sha256).hexdigest()
    exito = proveedor.dar_aval(avalador_ref, avalado_ident, conv_id)
    conn.close()
    if not exito:
        raise HTTPException(400, "Avalador excedió tope de avales")
    return {"avalador": avalador_credencial, "avalado": avalado_ident, "exito": True}

@app.get("/convocatorias/{conv_id}/escrutinio")
async def escrutinio(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    conn = _get_conn()
    row = conn.execute(
        "SELECT estado, opciones_json, titulo, emisor_pub_hex FROM convocatorias WHERE id = ?",
        (conv_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    estado, opciones_json, titulo, emisor_pub_hex = row
    if estado not in ("cerrada", "escrutada", "archivada"):
        conn.close()
        raise HTTPException(400, f"Escrutinio solo disponible para convocatorias cerradas (estado: {estado})")
    opciones = json.loads(opciones_json)
    recuento = {}
    for opcion in opciones:
        count = conn.execute(
            "SELECT COUNT(*) FROM votos WHERE convocatoria_id = ? AND opcion = ?",
            (conv_id, opcion)
        ).fetchone()[0]
        recuento[opcion] = count
    total_votos = sum(recuento.values())
    emisiones_completadas = conn.execute(
        "SELECT COUNT(*) FROM emisiones WHERE convocatoria_id = ? AND estado = 'completada'",
        (conv_id,)
    ).fetchone()[0]
    personas_censo = conn.execute(
        "SELECT COUNT(*) FROM personas WHERE convocatoria_id = ?",
        (conv_id,)
    ).fetchone()[0]
    votos = conn.execute(
        "SELECT r_prima, s_prima, opcion FROM votos WHERE convocatoria_id = ? ORDER BY r_prima",
        (conv_id,)
    ).fetchall()
    urna_data = b""
    for r_prima, s_prima, opcion in votos:
        urna_data += r_prima + s_prima + opcion.encode()
    urna_sha256 = hashlib.sha256(urna_data).hexdigest()
    conn.close()
    return {
        "convocatoria_id": conv_id,
        "titulo": titulo,
        "estado": estado,
        "emisor_pub_hex": emisor_pub_hex,
        "opciones": opciones,
        "recuento": recuento,
        "total_votos": total_votos,
        "emisiones_completadas": emisiones_completadas,
        "personas_en_censo": personas_censo,
        "participacion": f"{(total_votos / personas_censo * 100):.1f}%" if personas_censo > 0 else "N/A",
        "urna_sha256": urna_sha256,
        "verificacion": f"python scripts/verificador_independiente.py {conv_id}"
    }

@app.get("/convocatorias/{conv_id}/urna")
async def descargar_urna(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    conn = _get_conn()
    row = conn.execute(
        "SELECT estado, emisor_pub_hex FROM convocatorias WHERE id = ?",
        (conv_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Convocatoria no encontrada")
    estado, emisor_pub_hex = row
    if estado not in ("cerrada", "escrutada", "archivada"):
        conn.close()
        raise HTTPException(400, f"Urna solo disponible para convocatorias cerradas (estado: {estado})")
    votos = conn.execute(
        "SELECT r_prima, s_prima, opcion FROM votos WHERE convocatoria_id = ? ORDER BY r_prima",
        (conv_id,)
    ).fetchall()
    conn.close()
    return {
        "convocatoria_id": conv_id,
        "emisor_pub_hex": emisor_pub_hex,
        "total_votos": len(votos),
        "votos": [
            {"r_prima": r.hex(), "s_prima": s.hex(), "opcion": op}
            for r, s, op in votos
        ]
    }

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
