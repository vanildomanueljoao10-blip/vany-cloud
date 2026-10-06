# ============================================================
# VANY CLOUD GAME v1
# Cloud Gaming Manager
# Engine: Vany API 05.6
# ============================================================

import sqlite3
import secrets
import time
from datetime import datetime

DATABASE = "vany_cloud_game.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_cloud_game_db():
    db = get_db()
    cur = db.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cloud_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            email TEXT UNIQUE,
            plan TEXT DEFAULT 'free',
            credits INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # GAMES
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cloud_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'game',
            image TEXT DEFAULT '',
            executable TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # SERVERS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cloud_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            region TEXT DEFAULT 'global',
            host TEXT DEFAULT '',
            port INTEGER DEFAULT 0,
            gpu TEXT DEFAULT '',
            status TEXT DEFAULT 'offline',
            current_game TEXT DEFAULT '',
            current_session TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # SESSIONS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cloud_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            game_id TEXT NOT NULL,
            server_id TEXT DEFAULT '',
            status TEXT DEFAULT 'starting',
            started_at TEXT NOT NULL,
            ended_at TEXT DEFAULT '',
            duration_seconds INTEGER DEFAULT 0
        )
    """)

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cloud_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            game_id TEXT NOT NULL,
            duration_seconds INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # DEFAULT GAMES
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM cloud_games
    """)

    total_games = cur.fetchone()["total"]

    if total_games == 0:

        now = datetime.utcnow().isoformat()

        games = [
            (
                "vany-football",
                "Vany Football",
                "Jogo de futebol da plataforma Vany.",
                "football",
                "",
                "",
                "active",
                now
            ),
            (
                "vany-racing",
                "Vany Racing",
                "Jogo de corrida para testes do Vany Cloud Game.",
                "racing",
                "",
                "",
                "active",
                now
            ),
            (
                "vany-city",
                "Vany City",
                "Experiência de cidade virtual da Vany.",
                "open-world",
                "",
                "",
                "active",
                now
            )
        ]

        cur.executemany("""
            INSERT INTO cloud_games (
                game_id,
                name,
                description,
                category,
                image,
                executable,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, games)

    # --------------------------------------------------------
    # DEFAULT SERVER
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM cloud_servers
    """)

    total_servers = cur.fetchone()["total"]

    if total_servers == 0:

        now = datetime.utcnow().isoformat()

        cur.execute("""
            INSERT INTO cloud_servers (
                server_id,
                name,
                region,
                host,
                port,
                gpu,
                status,
                current_game,
                current_session,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "vany-server-01",
            "Vany Server 01",
            "global",
            "",
            0,
            "GPU-PENDING",
            "offline",
            "",
            "",
            now
        ))

    db.commit()
    db.close()


# ============================================================
# USERS
# ============================================================

def create_user(username, email=None, plan="free"):

    db = get_db()

    user_id = "vny_user_" + secrets.token_hex(8)

    now = datetime.utcnow().isoformat()

    try:

        db.execute("""
            INSERT INTO cloud_users (
                user_id,
                username,
                email,
                plan,
                credits,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            username,
            email,
            plan,
            60,
            now
        ))

        db.commit()

        result = {
            "success": True,
            "user_id": user_id,
            "username": username,
            "plan": plan,
            "credits": 60
        }

    except sqlite3.IntegrityError:

        result = {
            "success": False,
            "error": "user_already_exists"
        }

    db.close()

    return result


def get_user(user_id):

    db = get_db()

    row = db.execute("""
        SELECT *
        FROM cloud_users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    db.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# GAMES
# ============================================================

def list_games():

    db = get_db()

    rows = db.execute("""
        SELECT *
        FROM cloud_games
        WHERE status = 'active'
        ORDER BY id DESC
    """).fetchall()

    db.close()

    return [dict(row) for row in rows]


def get_game(game_id):

    db = get_db()

    row = db.execute("""
        SELECT *
        FROM cloud_games
        WHERE game_id = ?
    """, (game_id,)).fetchone()

    db.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# SERVERS
# ============================================================

def list_servers():

    db = get_db()

    rows = db.execute("""
        SELECT *
        FROM cloud_servers
        ORDER BY id ASC
    """).fetchall()

    db.close()

    return [dict(row) for row in rows]


def get_available_server():

    db = get_db()

    row = db.execute("""
        SELECT *
        FROM cloud_servers
        WHERE status = 'online'
        AND current_session = ''
        LIMIT 1
    """).fetchone()

    db.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# SESSIONS
# ============================================================

def start_session(user_id, game_id):

    user = get_user(user_id)

    if user is None:

        return {
            "success": False,
            "error": "user_not_found"
        }

    game = get_game(game_id)

    if game is None:

        return {
            "success": False,
            "error": "game_not_found"
        }

    # --------------------------------------------------------
    # CHECK ACTIVE SESSION
    # --------------------------------------------------------

    db = get_db()

    active = db.execute("""
        SELECT *
        FROM cloud_sessions
        WHERE user_id = ?
        AND status IN ('starting', 'connecting', 'running')
        LIMIT 1
    """, (user_id,)).fetchone()

    db.close()

    if active:

        return {
            "success": False,
            "error": "active_session_exists",
            "session": dict(active)
        }

    # --------------------------------------------------------
    # CHECK CREDITS
    # --------------------------------------------------------

    if user["credits"] <= 0:

        return {
            "success": False,
            "error": "no_credits"
        }

    # --------------------------------------------------------
    # FIND SERVER
    # --------------------------------------------------------

    server = get_available_server()

    # --------------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------------

    session_id = "vny_session_" + secrets.token_hex(10)

    now = datetime.utcnow().isoformat()

    if server:

        status = "connecting"
        server_id = server["server_id"]

    else:

        status = "waiting_server"
        server_id = ""

    db = get_db()

    db.execute("""
        INSERT INTO cloud_sessions (
            session_id,
            user_id,
            game_id,
            server_id,
            status,
            started_at,
            ended_at,
            duration_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        user_id,
        game_id,
        server_id,
        status,
        now,
        "",
        0
    ))

    # Reserve server
    if server:

        db.execute("""
            UPDATE cloud_servers
            SET current_session = ?,
                current_game = ?,
                status = 'busy'
            WHERE server_id = ?
        """, (
            session_id,
            game_id,
            server["server_id"]
        ))

    # Consume one credit for the initial session reservation
    db.execute("""
        UPDATE cloud_users
        SET credits = credits - 1
        WHERE user_id = ?
        AND credits > 0
    """, (user_id,))

    db.commit()
    db.close()

    return {
        "success": True,
        "session_id": session_id,
        "user_id": user_id,
        "game_id": game_id,
        "server_id": server_id,
        "status": status,
        "stream": {
            "ready": False,
            "protocol": "pending",
            "url": ""
        }
    }


def get_session(session_id):

    db = get_db()

    row = db.execute("""
        SELECT *
        FROM cloud_sessions
        WHERE session_id = ?
    """, (session_id,)).fetchone()

    db.close()

    if row is None:
        return None

    return dict(row)


def stop_session(session_id):

    session = get_session(session_id)

    if session is None:

        return {
            "success": False,
            "error": "session_not_found"
        }

    if session["status"] == "stopped":

        return {
            "success": True,
            "already_stopped": True,
            "session": session
        }

    started_at = session["started_at"]

    try:

        start_time = datetime.fromisoformat(started_at)

        duration = int(
            (datetime.utcnow() - start_time).total_seconds()
        )

    except Exception:

        duration = 0

    now = datetime.utcnow().isoformat()

    db = get_db()

    db.execute("""
        UPDATE cloud_sessions
        SET status = 'stopped',
            ended_at = ?,
            duration_seconds = ?
        WHERE session_id = ?
    """, (
        now,
        duration,
        session_id
    ))

    # Free server
    if session["server_id"]:

        db.execute("""
            UPDATE cloud_servers
            SET current_session = '',
                current_game = '',
                status = 'online'
            WHERE server_id = ?
        """, (
            session["server_id"],
        ))

    # Save history
    db.execute("""
        INSERT INTO cloud_history (
            session_id,
            user_id,
            game_id,
            duration_seconds,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        session_id,
        session["user_id"],
        session["game_id"],
        duration,
        now
    ))

    db.commit()
    db.close()

    return {
        "success": True,
        "session_id": session_id,
        "status": "stopped",
        "duration_seconds": duration
    }


# ============================================================
# HISTORY
# ============================================================

def get_history(user_id):

    db = get_db()

    rows = db.execute("""
        SELECT
            h.*,
            g.name AS game_name
        FROM cloud_history h
        LEFT JOIN cloud_games g
        ON h.game_id = g.game_id
        WHERE h.user_id = ?
        ORDER BY h.id DESC
    """, (user_id,)).fetchall()

    db.close()

    return [dict(row) for row in rows]


# ============================================================
# PLANS
# ============================================================

def get_plans():

    return [
        {
            "id": "free",
            "name": "Vany Free",
            "credits": 60,
            "priority": 0,
            "quality": "standard"
        },
        {
            "id": "pro",
            "name": "Vany Pro",
            "credits": 600,
            "priority": 1,
            "quality": "high"
        }
    ]


# ============================================================
# CREDITS
# ============================================================

def get_credits(user_id):

    user = get_user(user_id)

    if user is None:

        return {
            "success": False,
            "error": "user_not_found"
        }

    return {
        "success": True,
        "user_id": user_id,
        "plan": user["plan"],
        "credits": user["credits"]
    }


# ============================================================
# SERVER CONTROL
# ============================================================

def set_server_status(server_id, status):

    allowed = [
        "online",
        "offline",
        "maintenance"
    ]

    if status not in allowed:

        return {
            "success": False,
            "error": "invalid_status"
        }

    db = get_db()

    cur = db.execute("""
        UPDATE cloud_servers
        SET status = ?
        WHERE server_id = ?
    """, (
        status,
        server_id
    ))

    db.commit()

    changed = cur.rowcount

    db.close()

    if changed == 0:

        return {
            "success": False,
            "error": "server_not_found"
        }

    return {
        "success": True,
        "server_id": server_id,
        "status": status
    }


# ============================================================
# HEALTH
# ============================================================

def cloud_game_health():

    db = get_db()

    games = db.execute("""
        SELECT COUNT(*) AS total
        FROM cloud_games
    """).fetchone()["total"]

    servers = db.execute("""
        SELECT COUNT(*) AS total
        FROM cloud_servers
    """).fetchone()["total"]

    active_sessions = db.execute("""
        SELECT COUNT(*) AS total
        FROM cloud_sessions
        WHERE status IN (
            'starting',
            'connecting',
            'running'
        )
    """).fetchone()["total"]

    db.close()

    return {
        "service": "Vany Cloud Game",
        "version": "1.0.0",
        "engine": "05.6",
        "status": "ok",
        "games": games,
        "servers": servers,
        "active_sessions": active_sessions,
        "streaming": "pending_gpu"
    }


# ============================================================
# INITIALIZE
# ============================================================

init_cloud_game_db()
