# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""T2/T5: clave maestra fail-closed y derivación de claves por convocatoria."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from coincurve import PrivateKey

import claves

RAIZ = Path(__file__).parent.parent
OK = "ab" * 32


def test_clave_desde_env():
    assert claves.cargar_clave_maestra({"PANRAP_EMISOR_KEY_HEX": OK}, Path("/nonexistent")) == bytes.fromhex(OK)


@pytest.mark.parametrize("valor", ["ab" * 31, "ab" * 33, "zz" * 32, "00" * 32, "00" * 31 + "01"])
def test_clave_env_invalida_o_debil(valor):
    with pytest.raises(RuntimeError):
        claves.cargar_clave_maestra({"PANRAP_EMISOR_KEY_HEX": valor}, Path("/nonexistent"))


def test_sin_clave_falla_salvo_efimera(tmp_path):
    with pytest.raises(RuntimeError, match="clave"):
        claves.cargar_clave_maestra({}, tmp_path)
    assert len(claves.cargar_clave_maestra({"PANRAP_ALLOW_EPHEMERAL_KEY": "1"}, tmp_path)) == 32


def test_fichero_con_permisos(tmp_path):
    f = tmp_path / "clave_emisor.hex"
    f.write_text(OK + "\n")
    os.chmod(f, 0o644)
    with pytest.raises(RuntimeError, match="permisos"):
        claves.cargar_clave_maestra({}, tmp_path)
    os.chmod(f, 0o600)
    assert claves.cargar_clave_maestra({}, tmp_path) == bytes.fromhex(OK)


def test_derivacion_determinista_y_separada():
    m1, m2 = bytes.fromhex(OK), bytes.fromhex("cd" * 32)
    a = claves.derivar_clave_convocatoria(m1, "conv-A")
    assert a == claves.derivar_clave_convocatoria(m1, "conv-A")
    assert a != claves.derivar_clave_convocatoria(m1, "conv-B")
    assert a != claves.derivar_clave_convocatoria(m2, "conv-A")
    PrivateKey(a)  # escalar válido


def _importar_main(env_extra):
    env = {"PATH": os.environ["PATH"], **env_extra}
    return subprocess.run([sys.executable, "-c", "import main"], cwd=RAIZ, env=env, capture_output=True, text=True)


def test_main_no_arranca_sin_clave():
    r = _importar_main({})
    assert r.returncode != 0 and "clave" in r.stderr.lower()


def test_main_arranca_con_clave_efimera_permitida():
    assert _importar_main({"PANRAP_ALLOW_EPHEMERAL_KEY": "1"}).returncode == 0


def test_clave_emisor_hex_ignorada_por_git():
    r = subprocess.run(["git", "check-ignore", "-q", "clave_emisor.hex"], cwd=RAIZ)
    assert r.returncode == 0
