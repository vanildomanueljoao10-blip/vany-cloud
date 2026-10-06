import sqlite3
import uuid
from datetime import datetime, timezone, timedelta


DB_FILE = "vany_premium.db"


class PremiumManager:

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.db_file)

    def init_db(self):
        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS premium_users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            plan TEXT NOT NULL DEFAULT 'free',
            premium_status TEXT NOT NULL DEFAULT 'inactive',
            premium_until TEXT,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS premium_payments (
            payment_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            method TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'MZN',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            confirmed_at TEXT,
            premium_days INTEGER NOT NULL DEFAULT 30
        )
        """)

        db.commit()
        db.close()

    def create_user(self, user_id, name="", email=""):
        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        INSERT OR IGNORE INTO premium_users
        (user_id, name, email, plan, premium_status, created_at)
        VALUES (?, ?, ?, 'free', 'inactive', ?)
        """, (
            user_id,
            name,
            email,
            self.now()
        ))

        db.commit()
        db.close()

        return self.get_user(user_id)

    def get_user(self, user_id):
        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        SELECT
            user_id,
            name,
            email,
            plan,
            premium_status,
            premium_until,
            created_at
        FROM premium_users
        WHERE user_id = ?
        """, (user_id,))

        row = cur.fetchone()
        db.close()

        if not row:
            return None

        return {
            "user_id": row[0],
            "name": row[1],
            "email": row[2],
            "plan": row[3],
            "premium_status": row[4],
            "premium_until": row[5],
            "created_at": row[6]
        }

    def create_payment(self, user_id, method):
        method = method.lower().strip()

        if method not in ("mpesa", "emola"):
            raise ValueError("Método de pagamento inválido")

        user = self.get_user(user_id)

        if not user:
            self.create_user(user_id)
            
        payment_id = "vny_pay_" + uuid.uuid4().hex[:16]

        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        INSERT INTO premium_payments
        (
            payment_id,
            user_id,
            method,
            amount,
            currency,
            status,
            created_at,
            premium_days
        )
        VALUES (?, ?, ?, ?, 'MZN', 'pending', ?, 30)
        """, (
            payment_id,
            user_id,
            method,
            499,
            self.now()
        ))

        db.commit()
        db.close()

        return self.get_payment(payment_id)

    def get_payment(self, payment_id):
        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        SELECT
            payment_id,
            user_id,
            method,
            amount,
            currency,
            status,
            created_at,
            confirmed_at,
            premium_days
        FROM premium_payments
        WHERE payment_id = ?
        """, (payment_id,))

        row = cur.fetchone()
        db.close()

        if not row:
            return None

        return {
            "payment_id": row[0],
            "user_id": row[1],
            "method": row[2],
            "amount": row[3],
            "currency": row[4],
            "status": row[5],
            "created_at": row[6],
            "confirmed_at": row[7],
            "premium_days": row[8]
        }

    def confirm_payment(self, payment_id):
        payment = self.get_payment(payment_id)

        if not payment:
            raise ValueError("Pagamento não encontrado")

        if payment["status"] == "confirmed":
            return self.get_user(payment["user_id"])

        now = datetime.now(timezone.utc)

        user = self.get_user(payment["user_id"])

        if not user:
            self.create_user(payment["user_id"])
            user = self.get_user(payment["user_id"])

        if user["premium_until"]:
            try:
                current_until = datetime.fromisoformat(
                    user["premium_until"]
                )

                if current_until > now:
                    start = current_until
                else:
                    start = now

            except Exception:
                start = now
        else:
            start = now

        premium_until = start + timedelta(
            days=payment["premium_days"]
        )

        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        UPDATE premium_payments
        SET
            status = 'confirmed',
            confirmed_at = ?
        WHERE payment_id = ?
        """, (
            self.now(),
            payment_id
        ))

        cur.execute("""
        UPDATE premium_users
        SET
            plan = 'premium',
            premium_status = 'active',
            premium_until = ?
        WHERE user_id = ?
        """, (
            premium_until.isoformat(),
            payment["user_id"]
        ))

        db.commit()
        db.close()

        return self.get_user(payment["user_id"])

    def cancel_payment(self, payment_id):
        db = self.connect()
        cur = db.cursor()

        cur.execute("""
        UPDATE premium_payments
        SET status = 'cancelled'
        WHERE payment_id = ?
        AND status = 'pending'
        """, (payment_id,))

        db.commit()
        changed = cur.rowcount
        db.close()

        return changed > 0

    def check_expired(self, user_id):
        user = self.get_user(user_id)

        if not user:
            return None

        if user["premium_status"] != "active":
            return user

        if not user["premium_until"]:
            return user

        try:
            until = datetime.fromisoformat(
                user["premium_until"]
            )

            now = datetime.now(timezone.utc)

            if until <= now:
                db = self.connect()
                cur = db.cursor()

                cur.execute("""
                UPDATE premium_users
                SET
                    plan = 'free',
                    premium_status = 'expired'
                WHERE user_id = ?
                """, (user_id,))

                db.commit()
                db.close()

                return self.get_user(user_id)

        except Exception:
            pass

        return user

    def now(self):
        return datetime.now(timezone.utc).isoformat()


premium_manager = PremiumManager()
