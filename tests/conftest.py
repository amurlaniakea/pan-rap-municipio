# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
import sqlite3, pytest, tempfile, os
from pathlib import Path

# Antes de importar main: clave efímera permitida solo en tests y token de administración conocido.
os.environ.setdefault("PANRAP_ALLOW_EPHEMERAL_KEY", "1")
os.environ.setdefault("PANRAP_ADMIN_TOKEN", "t" * 32)

@pytest.fixture(scope="session", autouse=True)
def db_temporal():
    """Crea una BD temporal en disco compartida por todos los tests de la sesión."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["PANRAP_DB"] = db_path
    conn = sqlite3.connect(db_path)
    conn.executescript((Path(__file__).parent.parent / "backend" / "schema.sql").read_text())
    conn.commit()
    conn.close()
    yield db_path
    try:
        os.unlink(db_path)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def limpiar_datos(db_temporal):
    conn = sqlite3.connect(db_temporal)
    conn.execute("DELETE FROM votos")
    conn.execute("DELETE FROM emisiones")
    conn.execute("DELETE FROM personas")
    conn.execute("DELETE FROM convocatorias")
    conn.commit()
    conn.close()
    yield

@pytest.fixture(autouse=True)
def reset_emisor(monkeypatch):
    import main
    main._emisores.clear()
    return

@pytest.fixture
def test_client():
    import main
    from fastapi.testclient import TestClient
    return TestClient(main.app)


class Api:
    """Cliente de la API: .client sin credenciales y .admin con la cabecera de administración."""
    def __init__(self, client):
        self.client = client
        self.admin = {"X-Admin-Token": os.environ["PANRAP_ADMIN_TOKEN"]}


@pytest.fixture
def api():
    import main
    from fastapi.testclient import TestClient
    return Api(TestClient(main.app))
