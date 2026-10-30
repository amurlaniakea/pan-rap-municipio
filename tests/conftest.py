# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
import sqlite3, pytest, tempfile, os
from pathlib import Path

@pytest.fixture(scope="function", autouse=True)
def app_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript((Path(__file__).parent.parent / "backend" / "schema.sql").read_text())
    conn.commit()
    # Expone la conexión en memoria al entorno de prueba; no persiste archivo en disco
    monkeypatch.setenv("PANRAP_DB", ":memory:")
    return conn

@pytest.fixture(scope="function", autouse=True)
def reset_emisor(monkeypatch):
    import main
    main.emisor._sesion = None
    return

@pytest.fixture
def test_client():
    import main
    from fastapi.testclient import TestClient
    return TestClient(main.app)
