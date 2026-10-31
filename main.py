# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""API FastAPI — Blind Schnorr sobre secp256k1 (Fase 6a: integridad del flujo).

Modelo de confianza: ver docs/04-modelo-de-confianza.md. Emisor y urna viven en este mismo proceso."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException

from elegibilidad import Padron

# Regla S4: toda aritmética con secretos pasa por coincurve (Emisor)
from emisor_schnorr import Emisor, EmisionOcupada, SesionInvalida, EntradaInvalida
import urna_schnorr
import claves
from urna_publica import urna_sha256

SCHEMA_VERSION = 2
MAX_INTENTOS = 3
MENSAJE_GENERICO = "Credencial inválida o ya utilizada"
_ESTADOS_ABIERTOS = ("emision", "votacion")
_OPCION_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

DB_PATH = lambda: os.getenv("PANRAP_DB", str(Path(__file__).parent / "panrap.db"))

# Clave maestra: fail-closed si no está configurada (D11). Cada convocatoria firma con su clave derivada (D7).
_MASTER = claves.cargar_clave_maestra()
_emisores: dict[str, Emisor] = {}


def _emisor_de(conv_id: str) -> Emisor:
    """Emisor de la convocatoria. Llamar solo con ids ya comprobados en la BD."""
    em = _emisores.get(conv_id)
    if em is None:
        em = _emisores[conv_id] = Emisor(claves.derivar_clave_convocatoria(_MASTER, conv_id))
    return em


def _validar_convocatoria_id(conv_id: str) -> bool:
    if not isinstance(conv_id, str) or len(conv_id) == 0 or len(conv_id) > 64:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", conv_id))


def _get_conn():
    conn = sqlite3.connect(DB_PATH(), isolation_level=None)  # autocommit; las transacciones son explícitas
    if conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0:
        conn.executescript((Path(__file__).parent / "backend" / "schema.sql").read_text())
    else:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            conn.close()
            raise RuntimeError(f"Esquema de BD v{version}; se requiere v{SCHEMA_VERSION}. Crea una BD nueva.")
    return conn


@contextmanager
def _tx(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def require_admin(x_admin_token: str | None = Header(default=None)):
    esperado = os.getenv("PANRAP_ADMIN_TOKEN", "")
    if len(esperado) < 32:
        raise HTTPException(503, "Administración no configurada")
    if x_admin_token is None or not secrets.compare_digest(x_admin_token.encode(), esperado.encode()):
        raise HTTPException(403, "Token de administración inválido")


ADMIN = [Depends(require_admin)]

app = FastAPI()


# ---------- validación de entrada ----------

def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise HTTPException(400, f"{nombre} debe ser un texto no vacío")
    return valor


def _opciones(valor):
    if (not isinstance(valor, list) or not 2 <= len(valor) <= 16
            or not all(isinstance(o, str) and _OPCION_RE.match(o) for o in valor)
            or len(set(valor)) != len(valor)):
        raise HTTPException(400, "opciones: lista de 2 a 16 textos únicos con caracteres [A-Za-z0-9_-] (máx. 32)")
    return valor


def _fecha(valor, nombre):
    if valor is None:
        return None
    try:
        if not isinstance(valor, str):
            raise ValueError
        return datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(400, f"{nombre} debe ser una fecha ISO-8601")


def _fechas(emision, voto, cierre):
    f = [_fecha(emision, "emision_abre_en"), _fecha(voto, "voto_abre_en"), _fecha(cierre, "cierra_en")]
    if all(x is not None for x in f):
        try:
            ok = f[0] <= f[1] <= f[2]
        except TypeError:
            raise HTTPException(400, "Las fechas deben ser todas con o todas sin zona horaria")
        if not ok:
            raise HTTPException(400, "Se requiere emision_abre_en <= voto_abre_en <= cierra_en")


def _identificador(valor):
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 128:
        raise HTTPException(400, "Identificador inválido (texto de 1 a 128 caracteres)")
    return valor.strip()


# ---------- ciclo de vida ----------

@app.patch("/convocatorias/{conv_id}/estado", dependencies=ADMIN)
async def cambiar_estado(conv_id: str, payload: dict = {}):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    nuevo_estado = payload.get("estado")
    estados_validos = ["borrador", "programada", "emision", "votacion", "cerrada", "escrutada", "archivada"]
    if nuevo_estado not in estados_validos:
        raise HTTPException(400, f"Estado inválido. Válidos: {estados_validos}")
    with closing(_get_conn()) as conn:
        row = conn.execute("SELECT estado FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not row:
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
            raise HTTPException(400, f"Transición no permitida: {estado_actual} → {nuevo_estado}")
        if estado_actual == "borrador" and nuevo_estado == "programada":
            check = conn.execute(
                "SELECT titulo, texto_sha256, opciones_json, emision_abre_en, voto_abre_en, cierra_en FROM convocatorias WHERE id = ?",
                (conv_id,),
            ).fetchone()
            if not all(check):
                raise HTTPException(400, "Faltan campos obligatorios para programar")
        with _tx(conn):
            if nuevo_estado == "archivada":
                conn.execute("UPDATE convocatorias SET secreto_hmac = X'00' WHERE id = ?", (conv_id,))
            conn.execute("UPDATE convocatorias SET estado = ? WHERE id = ?", (nuevo_estado, conv_id))
    return {"id": conv_id, "estado_anterior": estado_actual, "estado_nuevo": nuevo_estado}


@app.patch("/convocatorias/{conv_id}", dependencies=ADMIN)
async def actualizar_convocatoria(conv_id: str, payload: dict = {}):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    updates, values = [], []
    if "titulo" in payload:
        updates.append("titulo = ?")
        values.append(_texto(payload["titulo"], "titulo"))
    if "texto" in payload:
        updates.append("texto_sha256 = ?")
        values.append(hashlib.sha256(_texto(payload["texto"], "texto").encode()).hexdigest())
    if "opciones" in payload:
        updates.append("opciones_json = ?")
        values.append(json.dumps(_opciones(payload["opciones"])))
    for campo in ("emision_abre_en", "voto_abre_en", "cierra_en"):
        if campo in payload:
            _fecha(payload[campo], campo)
            updates.append(f"{campo} = ?")
            values.append(payload[campo])
    with closing(_get_conn()) as conn:
        row = conn.execute("SELECT estado FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Convocatoria no encontrada")
        if row[0] != "borrador":
            raise HTTPException(400, "Solo se puede editar en estado borrador")
        if not updates:
            raise HTTPException(400, "No hay campos para actualizar")
        values.append(conv_id)
        conn.execute(f"UPDATE convocatorias SET {', '.join(updates)} WHERE id = ?", values)
    return {"id": conv_id, "actualizado": True}


@app.post("/convocatorias", status_code=201, dependencies=ADMIN)
async def crear_convocatoria(payload: dict):
    titulo = _texto(payload.get("titulo"), "titulo")
    texto = _texto(payload.get("texto"), "texto")
    opciones = _opciones(payload.get("opciones", ["a_favor", "en_contra", "abstencion"]))
    modo = payload.get("modo_elegibilidad", "padron")
    if modo != "padron":
        raise HTTPException(400, f"Modo de elegibilidad no implementado: {modo!r} (solo 'padron')")
    nivel = payload.get("nivel_garantia", "media")
    if nivel not in ("alta", "media", "baja"):
        raise HTTPException(400, "nivel_garantia debe ser alta, media o baja")
    emision_abre_en = payload.get("emision_abre_en")
    voto_abre_en = payload.get("voto_abre_en")
    cierra_en = payload.get("cierra_en")
    _fechas(emision_abre_en, voto_abre_en, cierra_en)
    conv_id = str(uuid.uuid4())
    Y = _emisor_de(conv_id).Y
    with closing(_get_conn()) as conn:
        conn.execute(
            "INSERT INTO convocatorias (id, propuesta_id, titulo, texto_sha256, opciones_json, modo_elegibilidad, nivel_garantia, emision_abre_en, voto_abre_en, cierra_en, estado, emisor_pub_hex, emisor_pub_sha256, secreto_hmac) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (conv_id, 1, titulo, hashlib.sha256(texto.encode()).hexdigest(), json.dumps(opciones), modo, nivel,
             emision_abre_en, voto_abre_en, cierra_en, "borrador", Y.hex(), hashlib.sha256(Y).hexdigest(),
             secrets.token_bytes(32)),
        )
    return {"id": conv_id, "estado": "borrador"}


@app.get("/convocatorias/{conv_id}")
async def ver_convocatoria(conv_id: str):
    """Datos públicos de la convocatoria, incluida la clave pública Y con la que se verifican sus votos."""
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    with closing(_get_conn()) as conn:
        row = conn.execute(
            "SELECT titulo, texto_sha256, opciones_json, modo_elegibilidad, estado, emisor_pub_hex, emisor_pub_sha256, emision_abre_en, voto_abre_en, cierra_en FROM convocatorias WHERE id = ?",
            (conv_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Convocatoria no encontrada")
    return {"id": conv_id, "titulo": row[0], "texto_sha256": row[1], "opciones": json.loads(row[2]),
            "modo_elegibilidad": row[3], "estado": row[4], "emisor_pub_hex": row[5],
            "emisor_pub_sha256": row[6], "emision_abre_en": row[7], "voto_abre_en": row[8], "cierra_en": row[9]}


# ---------- censo ----------

@app.post("/convocatorias/{conv_id}/censo", status_code=201, dependencies=ADMIN)
async def cargar_censo(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    identificadores = payload.get("identificadores")
    if not isinstance(identificadores, list) or len(identificadores) > 100_000:
        raise HTTPException(400, "identificadores debe ser una lista de hasta 100000 elementos")
    identificadores = [_identificador(i) for i in identificadores]
    with closing(_get_conn()) as conn:
        row = conn.execute("SELECT estado, secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Convocatoria no encontrada")
        if row[0] not in ("borrador", "programada"):
            raise HTTPException(400, f"Censo solo en borrador o programada (estado: {row[0]})")
        proveedor = Padron(row[1])
        nuevos = 0
        with _tx(conn):
            for ident in identificadores:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO personas (convocatoria_id, persona_ref) VALUES (?, ?)",
                    (conv_id, proveedor.derivar_ref(conv_id, ident)),
                )
                nuevos += cur.rowcount
    return {"convocatoria_id": conv_id, "recibidos": len(identificadores), "cargados": nuevos}


# ---------- emisión (firma ciega) ----------

@app.post("/convocatorias/{conv_id}/emision/inicio")
async def inicio(conv_id: str, payload: dict = {}):
    payload = payload or {}
    credencial = payload.get("credencial")
    if not credencial or not isinstance(credencial, str):
        raise HTTPException(status_code=400, detail="Falta credencial del usuario")
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    credencial = credencial.strip()
    if not 1 <= len(credencial) <= 128:
        raise HTTPException(status_code=400, detail=MENSAJE_GENERICO)
    with closing(_get_conn()) as conn:
        row = conn.execute("SELECT estado, secreto_hmac FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
        estado, secreto = row
        if estado not in _ESTADOS_ABIERTOS:
            raise HTTPException(status_code=400, detail=f"Convocatoria no abierta (estado: {estado})")
        ref = Padron(secreto).derivar_ref(conv_id, credencial)
        em = _emisor_de(conv_id)
        bloqueada = False
        with _tx(conn):
            if not conn.execute("SELECT 1 FROM personas WHERE convocatoria_id = ? AND persona_ref = ?",
                                (conv_id, ref)).fetchone():
                raise HTTPException(status_code=400, detail=MENSAJE_GENERICO)
            fila = conn.execute(
                "SELECT estado, sid, intentos FROM emisiones WHERE convocatoria_id = ? AND persona_ref = ?",
                (conv_id, ref),
            ).fetchone()
            if fila:
                est, sid_previo, intentos = fila
                if est != "pendiente":
                    raise HTTPException(status_code=400, detail=MENSAJE_GENERICO)
                if sid_previo is not None and em.sid_activo() == sid_previo:
                    raise HTTPException(status_code=503, detail="Servicio ocupado; reintente en 10s",
                                        headers={"Retry-After": "10"})
                if intentos >= MAX_INTENTOS:
                    conn.execute("UPDATE emisiones SET estado='bloqueada', sid=NULL WHERE convocatoria_id = ? AND persona_ref = ?",
                                 (conv_id, ref))
                    bloqueada = True
            if not bloqueada:
                try:
                    sid, R = em.inicio()  # S1: una sola sesión abierta por clave
                except EmisionOcupada:
                    raise HTTPException(status_code=503, detail="Servicio ocupado; reintente en 10s",
                                        headers={"Retry-After": "10"})
                if fila:
                    conn.execute("UPDATE emisiones SET sid = ?, intentos = intentos + 1 WHERE convocatoria_id = ? AND persona_ref = ?",
                                 (sid, conv_id, ref))
                else:
                    conn.execute("INSERT INTO emisiones (convocatoria_id, persona_ref, sid, estado, intentos) VALUES (?, ?, ?, 'pendiente', 1)",
                                 (conv_id, ref, sid))
        if bloqueada:
            raise HTTPException(status_code=400, detail=MENSAJE_GENERICO)
    return {"sid": sid, "R": R.hex()}


@app.post("/convocatorias/{conv_id}/emision/fin")
async def fin(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    sid, e_hex = payload.get("sesion"), payload.get("e")
    if not isinstance(sid, str) or not isinstance(e_hex, str):
        raise HTTPException(status_code=400, detail="Faltan sesion y e (texto hex)")
    try:
        e = bytes.fromhex(e_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="e no es hex válido")
    with closing(_get_conn()) as conn:
        if not conn.execute("SELECT 1 FROM convocatorias WHERE id = ?", (conv_id,)).fetchone():
            raise HTTPException(status_code=403, detail="Sesión inválida")
        em = _emisor_de(conv_id)
        with _tx(conn):
            fila = conn.execute(
                "SELECT persona_ref FROM emisiones WHERE convocatoria_id = ? AND sid = ? AND estado = 'pendiente'",
                (conv_id, sid),
            ).fetchone()
            if not fila:
                raise HTTPException(status_code=403, detail="Sesión inválida")
            # Se marca antes de liberar s; si em.fin falla, la transacción se revierte y no se libera nada.
            conn.execute("UPDATE emisiones SET estado = 'completada', sid = NULL WHERE convocatoria_id = ? AND persona_ref = ?",
                         (conv_id, fila[0]))
            try:
                s = em.fin(sid, e)
            except SesionInvalida as exc:
                raise HTTPException(status_code=403, detail=str(exc) or "Sesión inválida")
            except EntradaInvalida as exc:
                raise HTTPException(status_code=400, detail=str(exc) or "e inválido")
    return {"s": s.hex()}


# ---------- urna: escrutinio, acta, votos ----------

def _datos_urna(conn, conv_id):
    return conn.execute(
        "SELECT r_prima, s_prima, opcion FROM votos WHERE convocatoria_id = ? ORDER BY r_prima", (conv_id,)
    ).fetchall()


from io import BytesIO
from fastapi.responses import StreamingResponse


@app.post("/convocatorias/{conv_id}/acta", dependencies=ADMIN)
async def generar_acta(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    with closing(_get_conn()) as conn:
        row = conn.execute(
            "SELECT estado, titulo, opciones_json, emisor_pub_hex, emisor_pub_sha256 FROM convocatorias WHERE id = ?",
            (conv_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Convocatoria no encontrada")
        estado, titulo, opciones_json, emisor_pub_hex, emisor_pub_sha256 = row
        if estado != "escrutada":
            raise HTTPException(400, f"Acta solo para convocatorias escrutadas (estado: {estado})")
        opciones = json.loads(opciones_json)
        recuento = {o: conn.execute("SELECT COUNT(*) FROM votos WHERE convocatoria_id = ? AND opcion = ?",
                                    (conv_id, o)).fetchone()[0] for o in opciones}
        total_votos = sum(recuento.values())
        personas_censo = conn.execute("SELECT COUNT(*) FROM personas WHERE convocatoria_id = ?", (conv_id,)).fetchone()[0]
        urna_hash = urna_sha256(_datos_urna(conn, conv_id))
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
        c.drawString(50, y_pos, f"Urna SHA-256: {urna_hash}")
        y_pos -= 15
        c.drawString(50, y_pos, f"Emisor SHA-256: {emisor_pub_sha256}")
        c.setFont("Helvetica", 8)
        c.drawString(50, 50, "PAN-RAP — Tecnosfera Al Servicio De La Biosfera")
        c.drawString(50, 35, "Documento generado por sistema de votación anónima.")
        c.save()
        buffer.seek(0)
    except Exception as exc:
        raise HTTPException(500, f"Error generando PDF: {str(exc)}")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=acta_{conv_id}.pdf"})


@app.post("/convocatorias/{conv_id}/presencial/codigo", status_code=201, dependencies=ADMIN)
async def generar_codigo_presencial(conv_id: str, payload: dict):
    raise HTTPException(501, "Modo presencial no implementado (NO conectado a la emisión)")


@app.post("/convocatorias/{conv_id}/aval/dar", status_code=201, dependencies=ADMIN)
async def dar_aval(conv_id: str, payload: dict):
    raise HTTPException(501, "Modo aval no implementado (NO conectado a la emisión)")


@app.get("/convocatorias/{conv_id}/escrutinio")
async def escrutinio(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    with closing(_get_conn()) as conn:
        row = conn.execute(
            "SELECT estado, opciones_json, titulo, emisor_pub_hex FROM convocatorias WHERE id = ?", (conv_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Convocatoria no encontrada")
        estado, opciones_json, titulo, emisor_pub_hex = row
        if estado not in ("cerrada", "escrutada", "archivada"):
            raise HTTPException(400, f"Escrutinio solo disponible para convocatorias cerradas (estado: {estado})")
        opciones = json.loads(opciones_json)
        recuento = {o: conn.execute("SELECT COUNT(*) FROM votos WHERE convocatoria_id = ? AND opcion = ?",
                                    (conv_id, o)).fetchone()[0] for o in opciones}
        total_votos = sum(recuento.values())
        emisiones_completadas = conn.execute(
            "SELECT COUNT(*) FROM emisiones WHERE convocatoria_id = ? AND estado = 'completada'", (conv_id,)
        ).fetchone()[0]
        personas_censo = conn.execute("SELECT COUNT(*) FROM personas WHERE convocatoria_id = ?", (conv_id,)).fetchone()[0]
        urna_hash = urna_sha256(_datos_urna(conn, conv_id))
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
        "urna_sha256": urna_hash,
        "verificacion": f"python scripts/verificador_independiente.py {conv_id} --Y <clave publica del emisor>",
    }


@app.get("/convocatorias/{conv_id}/urna")
async def descargar_urna(conv_id: str):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(400, "convocatoria_id inválido")
    with closing(_get_conn()) as conn:
        row = conn.execute("SELECT estado, emisor_pub_hex FROM convocatorias WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Convocatoria no encontrada")
        estado, emisor_pub_hex = row
        if estado not in ("cerrada", "escrutada", "archivada"):
            raise HTTPException(400, f"Urna solo disponible para convocatorias cerradas (estado: {estado})")
        votos = _datos_urna(conn, conv_id)
    return {
        "convocatoria_id": conv_id,
        "emisor_pub_hex": emisor_pub_hex,
        "total_votos": len(votos),
        "urna_sha256": urna_sha256(votos),
        "votos": [{"r_prima": r.hex(), "s_prima": s.hex(), "opcion": op} for r, s, op in votos],
    }


@app.post("/convocatorias/{conv_id}/votos")
async def votar(conv_id: str, payload: dict):
    if not _validar_convocatoria_id(conv_id):
        raise HTTPException(status_code=400, detail="convocatoria_id inválido")
    opcion, r_hex, s_hex = payload.get("opcion"), payload.get("r_prima"), payload.get("s_prima")
    if not all(isinstance(x, str) and x for x in (opcion, r_hex, s_hex)):
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios")
    try:
        r_prima, s_prima = bytes.fromhex(r_hex), bytes.fromhex(s_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="r_prima y s_prima deben ser hex válido")
    if len(r_prima) != 33 or len(s_prima) != 32:
        raise HTTPException(status_code=400, detail="r_prima (33 bytes) o s_prima (32 bytes) con longitud incorrecta")
    with closing(_get_conn()) as conn:
        row = conn.execute(
            "SELECT estado, opciones_json, emisor_pub_hex FROM convocatorias WHERE id = ?", (conv_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
        estado, opciones_json, emisor_pub_hex = row
        if estado not in _ESTADOS_ABIERTOS:
            raise HTTPException(status_code=400, detail=f"Convocatoria no abierta para votar (estado: {estado})")
        if opcion not in json.loads(opciones_json):
            raise HTTPException(status_code=400, detail="Opción no válida para esta convocatoria")
        # La verificación usa la clave Y publicada de ESTA convocatoria (D7)
        if not urna_schnorr.verificar(bytes.fromhex(emisor_pub_hex), conv_id, opcion, r_prima, s_prima):
            raise HTTPException(status_code=400, detail="Verificación fallida")
        try:
            conn.execute("INSERT INTO votos (convocatoria_id, r_prima, s_prima, opcion) VALUES (?, ?, ?, ?)",
                         (conv_id, r_prima, s_prima, opcion))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(status_code=409, detail="Token gastado")
            raise
    return {"id": r_hex}
