#!/usr/bin/env python3
"""Create or update a ZAKI Server user.
Usage: python create_user.py <email> <password>
"""
import sys, os, sqlite3
from passlib.context import CryptContext

DB_PATH = os.environ.get("DB_PATH", "/opt/zaki-server/users.db")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    if len(sys.argv) != 3:
        print("Usage: python create_user.py <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1].strip().lower(), sys.argv[2]
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tenant TEXT NOT NULL DEFAULT 'mumtaz',
            active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    hashed = pwd_ctx.hash(password)
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?) "
        "ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash, active=1",
        (email, hashed)
    )
    conn.commit()
    conn.close()
    print(f"✅ User '{email}' created / updated.")


if __name__ == "__main__":
    main()
