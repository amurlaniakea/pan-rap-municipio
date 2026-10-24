#!/bin/bash
set -euo pipefail
REPO="/mnt/c/Users/Sil/Documents/GitHub/amurlaniakea/pan-rap-municipio"
cd "$REPO"
echo "[SETUP] Creando venv..."
python3 -m venv .venv
. ./.venv/bin/activate
echo "[SETUP] Instalando dependencias..."
pip install --quiet -r requirements.txt || echo "(algunas dependencias pueden no instalar; se continúa)"
echo "[SETUP] Inicializando DB..."
python3 -c "
import sqlite3, pathlib
c = sqlite3.connect('panrap.db')
c.executescript(pathlib.Path('backend/schema.sql').read_text())
print('DB inicializada.')
"
echo "[SETUP] Poblando seed..."
python3 -c "
import sqlite3, pathlib
c = sqlite3.connect('panrap.db')
c.executescript(pathlib.Path('scripts/seed_inicial.sql').read_text())
print('Seed poblado.')
"
echo "[SETUP] ÉXITO. Entorno listo. Para tests: pytest tests/"
