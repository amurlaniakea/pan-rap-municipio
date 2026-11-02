# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Guardas contra regresiones de honestidad del repositorio."""
import subprocess
from pathlib import Path

RAIZ = Path(__file__).parent.parent
FALSO = "PLACE" + "HOLDER"          # construido a trozos para que este fichero no se detecte a sí mismo
FRASES_FALSAS = ["Anonimato absoluto", "Transparencia total", "Los 4 modos funcionales"]


def _versionados():
    out = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split("\n")
    return [RAIZ / f for f in out if f]


def test_sin_marcadores_falsos_en_ficheros_versionados():
    malos = []
    for f in _versionados():
        try:
            if FALSO in f.read_text():
                malos.append(f.name)
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    assert not malos, f"marcadores falsos en: {malos}"


def test_readme_no_afirma_lo_que_no_es_cierto():
    readme = (RAIZ / "README.md").read_text()
    for frase in FRASES_FALSAS:
        assert frase not in readme, frase
    assert "prototipo" in readme.lower()


def test_scripts_y_main_sin_dependencias_no_declaradas():
    req = (RAIZ / "requirements.txt").read_text().lower()
    for f in [RAIZ / "main.py", *(RAIZ / "scripts").glob("*.py")]:
        assert "import requests" not in f.read_text() or "requests" in req, f.name


def test_paquete_de_auditoria_solo_cita_tests_que_existen():
    """Evita que docs/05-paquete-auditoria.md afirme pruebas que ya no existen o cambiaron de nombre."""
    import re
    doc = (RAIZ / "docs" / "05-paquete-auditoria.md").read_text()
    citados = re.findall(r"`?(test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)`?", doc)
    assert citados, "el paquete debería citar al menos una prueba concreta"
    # «::test_x» encadenados tras un fichero comparten fichero
    ficheros = re.findall(r"(test_[a-z0-9_]+\.py)((?:::test_[a-z0-9_]+(?:`, `)?)+)", doc)
    pares = {(f, n) for f, resto in ficheros for n in re.findall(r"test_[a-z0-9_]+", resto)} | set(citados)
    faltan = [(f, n) for f, n in sorted(pares) if f"def {n}(" not in (RAIZ / "tests" / f).read_text()]
    assert not faltan, f"pruebas citadas que no existen: {faltan}"
    for f in set(re.findall(r"`(test_[a-z0-9_]+\.py)`", doc)):
        assert (RAIZ / "tests" / f).exists(), f
