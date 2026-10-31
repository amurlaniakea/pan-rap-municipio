# SPDX-License-Identifier: AGPL-3.0-or-later
"""Acceso directo a la BD de pruebas (solo tests)."""
import sqlite3
from contextlib import closing

import main


def conn_db():
    return closing(sqlite3.connect(main.DB_PATH()))


def emisiones():
    with conn_db() as c:
        return c.execute("SELECT persona_ref, estado, intentos FROM emisiones ORDER BY persona_ref").fetchall()


def personas_cols():
    with conn_db() as c:
        return [r[1] for r in c.execute("PRAGMA table_info(personas)")]
