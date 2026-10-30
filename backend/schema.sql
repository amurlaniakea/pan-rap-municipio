CREATE TABLE IF NOT EXISTS emisiones (
  convocatoria_id TEXT NOT NULL,
  persona_ref TEXT NOT NULL,
  estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'completada', 'bloqueada')) DEFAULT 'pendiente',
  intentos INTEGER DEFAULT 0,
  PRIMARY KEY (convocatoria_id, persona_ref)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS votos (
  convocatoria_id TEXT NOT NULL,
  r_prima BLOB NOT NULL CHECK (length(r_prima) = 33),
  s_prima BLOB NOT NULL CHECK (length(s_prima) = 32),
  opcion VARCHAR(16) NOT NULL CHECK (opcion IN ('a_favor','en_contra','abstencion')),
  PRIMARY KEY (convocatoria_id, r_prima)
) WITHOUT ROWID;
