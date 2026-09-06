#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("vany_keys.db")


def conectar():
    return sqlite3.connect(DB_PATH)


def inicializar_usage():

    with conectar() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER,
                endpoint TEXT NOT NULL,
                model TEXT,
                status_code INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(api_key_id)
                    REFERENCES api_keys(id)
            )
        """)

        db.commit()


def registrar_usage(
    api_key_id,
    endpoint,
    model,
    status_code
):

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with conectar() as db:

        cursor = db.execute(
            """
            INSERT INTO api_usage
            (
                api_key_id,
                endpoint,
                model,
                status_code,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                api_key_id,
                endpoint,
                model,
                status_code,
                created_at
            )
        )

        db.commit()

        return cursor.lastrowid
