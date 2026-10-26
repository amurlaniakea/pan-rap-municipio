# PAN-RAP MUNICIPIO

Prototipo municipal para gobernanza cívica y participación ciudadana (~25.000 habitantes). Stack soberano, agnóstico al hosting.

Prototipo en desarrollo. No apto para uso real.

## Licencia
AGPL-3.0-or-later. Ver archivo LICENSE.

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
SPDX-License-Identifier: AGPL-3.0-or-later

## Entorno
Python 3.14. `pip install -r requirements.txt`; para ejecutar los tests, `pip install -r requirements-dev.txt`.

## Setup
bash scripts/setup_env.sh

## Tests
pytest tests/ -q   (la suite crea su propia base temporal)

## Lanzar (cuando exista)
fastapi dev main.py
