import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from server.config import settings


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    year INTEGER,
                    genre TEXT,
                    category TEXT,
                    description TEXT,
                    artwork_url TEXT,
                    thumbnail_path TEXT,
                    tags TEXT,
                    added_at TEXT NOT NULL,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS music (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL DEFAULT 'Unknown Artist',
                    album TEXT NOT NULL DEFAULT 'Unknown Album',
                    path TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    genre TEXT,
                    year INTEGER,
                    category TEXT,
                    description TEXT,
                    artwork_url TEXT,
                    thumbnail_path TEXT,
                    tags TEXT,
                    added_at TEXT NOT NULL,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS cloud_files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    folder TEXT NOT NULL DEFAULT '/',
                    uploaded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS libraries (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    media_type TEXT NOT NULL,
                    scanned_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    module_access TEXT NOT NULL DEFAULT 'all',
                    module_pins TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    module_access TEXT NOT NULL DEFAULT 'all',
                    unlocked_modules TEXT NOT NULL DEFAULT '',
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    media_type TEXT NOT NULL,
                    artwork_url TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS playlist_items (
                    id TEXT PRIMARY KEY,
                    playlist_id TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    media_kind TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id)
                );

                CREATE TABLE IF NOT EXISTS stream_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    media_kind TEXT NOT NULL,
                    media_title TEXT,
                    device_label TEXT,
                    user_agent TEXT,
                    ip_address TEXT,
                    started_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS active_streams (
                    stream_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    media_kind TEXT NOT NULL,
                    media_title TEXT,
                    device_label TEXT,
                    user_agent TEXT,
                    ip_address TEXT,
                    started_at TEXT NOT NULL,
                    last_ping_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

            for table, columns in {
                'videos': [
                    ('category', 'TEXT'),
                    ('description', 'TEXT'),
                    ('artwork_url', 'TEXT'),
                    ('thumbnail_path', 'TEXT'),
                    ('tags', 'TEXT'),
                    ('updated_at', 'TEXT'),
                ],
                'music': [
                    ('category', 'TEXT'),
                    ('description', 'TEXT'),
                    ('artwork_url', 'TEXT'),
                    ('thumbnail_path', 'TEXT'),
                    ('tags', 'TEXT'),
                    ('updated_at', 'TEXT'),
                ],
                'users': [
                    ('role', "TEXT NOT NULL DEFAULT 'user'"),
                    ('module_access', "TEXT NOT NULL DEFAULT 'all'"),
                    ('module_pins', "TEXT NOT NULL DEFAULT '{}'"),
                ],
                'sessions': [
                    ('role', "TEXT NOT NULL DEFAULT 'user'"),
                    ('module_access', "TEXT NOT NULL DEFAULT 'all'"),
                    ('unlocked_modules', "TEXT NOT NULL DEFAULT ''"),
                    ('ip_address', 'TEXT'),
                    ('user_agent', 'TEXT'),
                    ('last_seen_at', 'TEXT'),
                ],
            }.items():
                existing = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                for column_name, column_type in columns:
                    if column_name not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")

            conn.execute("UPDATE users SET module_access = 'all' WHERE module_access IS NULL OR TRIM(module_access) = ''")
            conn.execute("UPDATE sessions SET module_access = 'all' WHERE module_access IS NULL OR TRIM(module_access) = ''")
            conn.execute("UPDATE users SET module_pins = '{}' WHERE module_pins IS NULL OR TRIM(module_pins) = ''")
            conn.execute("UPDATE sessions SET unlocked_modules = '' WHERE unlocked_modules IS NULL")
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('module_pin_lock_enabled', 'false')"
            )

            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
            if admin_count == 0:
                first_user = conn.execute('SELECT id FROM users ORDER BY created_at ASC LIMIT 1').fetchone()
                if first_user:
                    conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (first_user['id'],))

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.connection() as conn:
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                (key, value),
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


db = Database()
