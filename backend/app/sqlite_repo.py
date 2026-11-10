"""SQLite repository used for local development and tests."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid4().hex


def filter_listings(listings: list[dict], *, q: str = "", category: str = "", owner_id: str = "", intent: str = ""):
    needle = q.strip().lower()
    results = []
    for listing in listings:
        if category and listing["category"] != category:
            continue
        if owner_id and listing["owner_id"] != owner_id:
            continue
        if intent and listing["intent"] != intent:
            continue
        if needle:
            haystack = " ".join(
                (listing["title"], listing["description"], listing["location"], listing["owner_name"])
            ).lower()
            if needle not in haystack:
                continue
        results.append(listing)
    results.sort(key=lambda item: item["created_at"], reverse=True)
    return results[:100]


class SqliteRepository:
    backend = "sqlite"

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def prepare(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT,
                    campus TEXT NOT NULL DEFAULT '',
                    bio TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    location TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    image_key TEXT,
                    status TEXT NOT NULL,
                    description_source TEXT NOT NULL,
                    category_source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS uploads (
                    image_key TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
                CREATE INDEX IF NOT EXISTS idx_listings_owner ON listings(owner_id);
                """
            )
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM notifications")
            self._conn.execute("DELETE FROM listings")
            self._conn.execute("DELETE FROM uploads")
            self._conn.execute("DELETE FROM users")
            self._conn.commit()

    def create_user(self, *, email: str, name: str, password_hash: str | None, campus: str, bio: str = "") -> dict:
        user = {
            "id": new_id(),
            "email": email.lower(),
            "name": name.strip(),
            "password_hash": password_hash,
            "campus": campus.strip(),
            "bio": bio,
            "created_at": utc_now(),
        }
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (id, email, name, password_hash, campus, bio, created_at)
                VALUES (:id, :email, :name, :password_hash, :campus, :bio, :created_at)
                """,
                user,
            )
            self._conn.commit()
        return self._public_user(user)

    def get_user_by_id(self, user_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._public_user(row) if row else None

    def get_user_by_email(self, email: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def update_user(self, user_id: str, changes: dict) -> dict | None:
        current = self.get_user_by_id(user_id)
        if not current:
            return None
        current.update(changes)
        with self._lock:
            self._conn.execute(
                "UPDATE users SET name = ?, campus = ?, bio = ? WHERE id = ?",
                (current["name"], current["campus"], current["bio"], user_id),
            )
            self._conn.commit()
        return self.get_user_by_id(user_id)

    def upsert_identity(self, *, user_id: str, email: str, name: str) -> dict:
        existing = self.get_user_by_id(user_id)
        if existing:
            return existing
        by_email = self.get_user_by_email(email)
        if by_email:
            return self._public_user(by_email)
        created_at = utc_now()
        record = {
            "id": user_id,
            "email": email.lower(),
            "name": name.strip() or email,
            "password_hash": None,
            "campus": "",
            "bio": "",
            "created_at": created_at,
        }
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (id, email, name, password_hash, campus, bio, created_at)
                VALUES (:id, :email, :name, :password_hash, :campus, :bio, :created_at)
                """,
                record,
            )
            self._conn.commit()
        return self._public_user(record)

    def add_upload(self, *, image_key: str, owner_id: str) -> dict:
        record = {"image_key": image_key, "owner_id": owner_id, "created_at": utc_now()}
        with self._lock:
            self._conn.execute(
                "INSERT INTO uploads (image_key, owner_id, created_at) VALUES (:image_key, :owner_id, :created_at)",
                record,
            )
            self._conn.commit()
        return record

    def get_upload(self, image_key: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM uploads WHERE image_key = ?", (image_key,)).fetchone()
        return dict(row) if row else None

    def delete_upload(self, image_key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM uploads WHERE image_key = ?", (image_key,))
            self._conn.commit()

    def create_listing(self, listing: dict) -> dict:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO listings (
                    id, owner_id, owner_name, title, description, category, intent, location,
                    contact, image_key, status, description_source, category_source, created_at, updated_at
                ) VALUES (
                    :id, :owner_id, :owner_name, :title, :description, :category, :intent, :location,
                    :contact, :image_key, :status, :description_source, :category_source, :created_at, :updated_at
                )
                """,
                listing,
            )
            self._conn.commit()
        return listing

    def get_listing(self, listing_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        return self._listing(row) if row else None

    def update_listing(self, listing: dict) -> dict:
        with self._lock:
            self._conn.execute(
                """
                UPDATE listings SET
                    owner_name = :owner_name,
                    title = :title,
                    description = :description,
                    category = :category,
                    intent = :intent,
                    location = :location,
                    contact = :contact,
                    image_key = :image_key,
                    status = :status,
                    description_source = :description_source,
                    category_source = :category_source,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                listing,
            )
            self._conn.commit()
        return listing

    def delete_listing(self, listing_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
            self._conn.commit()

    def list_listings(self, *, q: str = "", category: str = "", owner_id: str = "", intent: str = "") -> list[dict]:
        rows = self._conn.execute("SELECT * FROM listings").fetchall()
        listings = [self._listing(row) for row in rows]
        return filter_listings(listings, q=q, category=category, owner_id=owner_id, intent=intent)

    def add_notification(self, *, user_id: str, message: str, channel: str) -> dict:
        record = {
            "id": new_id(),
            "user_id": user_id,
            "message": message,
            "channel": channel,
            "read": False,
            "created_at": utc_now(),
        }
        stored = dict(record)
        stored["read"] = 0
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO notifications (id, user_id, message, channel, read, created_at)
                VALUES (:id, :user_id, :message, :channel, :read, :created_at)
                """,
                stored,
            )
            self._conn.commit()
        return record

    def list_notifications(self, user_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
        return [self._notification(row) for row in rows]

    def mark_notification_read(self, *, user_id: str, notification_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        if not row or row["user_id"] != user_id:
            return None
        with self._lock:
            self._conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
            self._conn.commit()
        updated = self._conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        return self._notification(updated)

    def _public_user(self, row) -> dict:
        data = dict(row)
        data.pop("password_hash", None)
        return data

    def _listing(self, row) -> dict:
        data = dict(row)
        if data.get("image_key") == "":
            data["image_key"] = None
        return data

    def _notification(self, row) -> dict:
        data = dict(row)
        data["read"] = bool(data["read"])
        return data
