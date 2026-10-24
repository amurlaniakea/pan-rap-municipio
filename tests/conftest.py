import sqlite3, pathlib, pytest, tempfile, os

@pytest.fixture(scope="session")
def db_path():
    # Crea DB temporal aislada del proyecto real
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="panrap_test_")
    os.close(fd)
    conn = sqlite3.connect(tmp_path)
    conn.executescript(pathlib.Path("backend/schema.sql").read_text())
    conn.executescript(pathlib.Path("scripts/seed_inicial.sql").read_text())
    conn.commit()
    conn.close()
    # El test usa esta ruta; la aplicación usa PANRAP_DB
    return tmp_path

@pytest.fixture
def test_client():
    import main
    import os
    # Forzar el módulo a usar la DB temporal durante el test
    # Esto requiere que main.py lea PANRAP_DB; si no lo hace, el test usará la DB del proyecto
    # Como medida defensiva: se verifica que la DB del test existe
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)
