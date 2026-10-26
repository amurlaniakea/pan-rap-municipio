# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
import sqlite3, pathlib, pytest, tempfile, os

@pytest.fixture(scope="function", autouse=True)
def app_db(monkeypatch):
    fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="panrap_test_")
    os.close(fd)
    conn = sqlite3.connect(tmp_path)
    from pathlib import Path
    conn.executescript((Path(__file__).parent.parent / "backend" / "schema.sql").read_text())
    conn.executescript((Path(__file__).parent.parent / "scripts" / "seed_inicial.sql").read_text())
    conn.commit()
    conn.close()
    monkeypatch.setenv("PANRAP_DB", tmp_path)
    return tmp_path

@pytest.fixture
def test_client():
    import main
    import os
    from fastapi.testclient import TestClient
    return TestClient(main.app)
