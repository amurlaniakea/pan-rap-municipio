#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "[SETUP] Creando venv..."
python3 -m venv .venv
. ./.venv/bin/activate
echo "[SETUP] Instalando dependencias..."
pip install -r requirements.txt
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
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
