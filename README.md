# PAN-RAP MUNICIPIO

Prototipo municipal para gobernanza cívica y participación ciudadana (~25.000 habitantes). Stack soberano, agnóstico al hosting.

Prototipo en desarrollo. No apto para uso real.

Motor criptográfico: **Blind Schnorr sobre secp256k1** (Fase 5, ver `03-motor-blind-schnorr.md`). La clave del emisor (`d`) se configura vía archivo (`tests/clave_real_ref.hex`) o variable de entorno; el verificador independiente (`scripts/verificador_independiente.py`) valida los votos públicos con `coincurve`.

## Licencia
AGPL-3.0-or-later. Ver archivo LICENSE.

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
SPDX-License-Identifier: AGPL-3.0-or-later

## Entorno
Python 3.12 (coincurve publica ruedas para 3.12). `pip install -r requirements.txt`; para los tests, `pip install -r requirements-dev.txt` o usar el `.venv` del proyecto.

## Setup
bash scripts/setup_env.sh

## Tests
pytest tests/ -q

## Lanzar
fastapi dev main.py

## Verificador independiente
python scripts/verificador_independiente.py
