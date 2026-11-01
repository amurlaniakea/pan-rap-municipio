-- Esquema v3 (Fase 7). BD con otro user_version se rechaza al arrancar (prototipo: sin migración).
CREATE TABLE IF NOT EXISTS personas (
  convocatoria_id TEXT NOT NULL,
  persona_ref TEXT NOT NULL,
  PRIMARY KEY (convocatoria_id, persona_ref)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS convocatorias (
  id TEXT PRIMARY KEY,
  propuesta_id INTEGER NOT NULL,
  titulo TEXT NOT NULL,
  texto_sha256 TEXT NOT NULL,
  opciones_json TEXT NOT NULL,
  modo_elegibilidad TEXT NOT NULL CHECK (modo_elegibilidad IN ('padron','presencial','aval','eid')) DEFAULT 'padron',
  nivel_garantia TEXT NOT NULL CHECK (nivel_garantia IN ('alta','media','baja')) DEFAULT 'media',
  censo_declarado INTEGER,
  emision_abre_en TEXT,
  voto_abre_en TEXT,
  cierra_en TEXT,
  estado TEXT NOT NULL DEFAULT 'borrador',
  emisor_pub_hex TEXT NOT NULL CHECK (length(emisor_pub_hex) = 66),
  emisor_pub_sha256 TEXT NOT NULL,
  log_pub_hex TEXT NOT NULL DEFAULT '',
  secreto_hmac BLOB NOT NULL DEFAULT X'00'
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS emisiones (
  convocatoria_id TEXT NOT NULL,
  persona_ref TEXT NOT NULL,
  sid TEXT,
  estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'completada', 'bloqueada')) DEFAULT 'pendiente',
  intentos INTEGER DEFAULT 0,
  PRIMARY KEY (convocatoria_id, persona_ref)
) WITHOUT ROWID;

-- lote: NULL hasta que el voto se sella en un checkpoint; después, el seq de ese checkpoint.
CREATE TABLE IF NOT EXISTS votos (
  convocatoria_id TEXT NOT NULL,
  r_prima BLOB NOT NULL CHECK (length(r_prima) = 33),
  s_prima BLOB NOT NULL CHECK (length(s_prima) = 32),
  opcion TEXT NOT NULL,
  lote INTEGER,
  PRIMARY KEY (convocatoria_id, r_prima)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS checkpoints (
  convocatoria_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  n INTEGER NOT NULL,
  root TEXT NOT NULL,
  prev TEXT NOT NULL,
  creado TEXT NOT NULL,
  firma TEXT NOT NULL,
  PRIMARY KEY (convocatoria_id, seq)
) WITHOUT ROWID;

PRAGMA user_version = 3;
