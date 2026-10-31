# SPDX-License-Identifier: AGPL-3.0-or-later
# Contrato rojo T0 — higiene del repo
import pytest, subprocess, pathlib, sys

@pytest.mark.xfail(strict=True, raises=(AssertionError, subprocess.CalledProcessError), reason="T0: .gitignore debe cubrir clave_emisor.hex; sin PLACEHOLDER; sin assert False en tests")
def test_higiene_repo():
    # Check .gitignore cubre clave_emisor.hex
    result = subprocess.run(["git", "check-ignore", "-q", "clave_emisor.hex"], capture_output=True)
    assert result.returncode == 0, "clave_emisor.hex no está ignorado"
    # Sin PLACEHOLDER en archivos versionados
    files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    for line in files:
        content = (pathlib.Path(__file__).parent.parent / line).read_text()
        assert "PLACEHOLDER" not in content, f"{line} contiene PLACEHOLDER"
    # Ningún test contiene assert False
    for f in subprocess.check_output(["git", "ls-files", "tests/"], text=True).splitlines():
        if f.endswith(".py"):
            content = (pathlib.Path(__file__).parent.parent / f).read_text()
            assert "assert False" not in content, f"{f} contiene assert False"
