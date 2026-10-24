# PAN-RAP MUNICIPIO

Prototipo municipal para gobernanza cívica y participación ciudadana (~25.000 habitantes). Stack soberano, agnóstico al hosting, con integración ECC y generación local de PDFs. Fase 1: diseño conceptual; código en desarrollo asistido riguroso (TDD + ECC).

## Licencia
AGPL-3.0-or-later. Ver archivo LICENSE (texto oficial GNU Affero General Public License v3).

## Setup
bash scripts/setup_env.sh

## Tests
pytest tests/ (fallan intencionalmente: TDD antes de API)

## Lanzar (cuando exista)
fastapi dev main.py
