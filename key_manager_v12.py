#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import hashlib
from pathlib import Path


DB_PATH = Path("vany_keys.db")


def conectar():

    return sqlite3.connect(DB_PATH)


def inicializar_banco():

    with conectar() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                key_hash TEXT NOT NULL UNIQUE,

                name TEXT NOT NULL,

                created_at TEXT NOT NULL,

                revoked INTEGER NOT NULL DEFAULT 0

            )
        """)

        db.commit()


def gerar_api_key():

    import secrets

    return (
        "vny_live_"
        + secrets.token_urlsafe(32)
    )


def criar_api_key(nome="Vany Developer"):

    from datetime import datetime, timezone

    api_key = gerar_api_key()

    key_hash = hash_api_key(
        api_key
    )

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with conectar() as db:

        cursor = db.execute(
            """
            INSERT INTO api_keys
            (
                key_hash,
                name,
                created_at,
                revoked
            )
            VALUES (?, ?, ?, 0)
            """,
            (
                key_hash,
                nome,
                created_at
            )
        )

        db.commit()

        key_id = cursor.lastrowid

    return {
        "id": key_id,
        "api_key": api_key,
        "name": nome,
        "created_at": created_at
    }


def revogar_api_key(key_id):

    with conectar() as db:

        cursor = db.execute(
            """
            UPDATE api_keys
            SET revoked = 1
            WHERE id = ?
              AND revoked = 0
            """,
            (key_id,)
        )

        db.commit()

        return cursor.rowcount > 0



def verificar_api_key(api_key):

    if not api_key:
        return False

    key_hash = hash_api_key(
        api_key
    )

    with conectar() as db:

        row = db.execute(
            """
            SELECT id
            FROM api_keys
            WHERE key_hash = ?
              AND revoked = 0
            LIMIT 1
            """,
            (key_hash,)
        ).fetchone()

    return row is not None


def hash_api_key(api_key):

    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":

    inicializar_banco()

    print("VANY KEY MANAGER V1.2")
    print("Banco:", DB_PATH)
    print("Banco inicializado com sucesso.")
