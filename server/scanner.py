import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mutagen import File as MutagenFile

from server.database import Database

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
MUSIC_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}


class MediaScanner:
    def __init__(self, database: Database) -> None:
        self.database = database

    def scan_folder(self, folder_path: str, media_type: str = 'all') -> dict[str, int]:
        root_path = Path(folder_path).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise FileNotFoundError(f'Folder does not exist: {root_path}')

        results = {'videos': 0, 'music': 0, 'duplicates': 0}

        for current_root, _, files in os.walk(root_path):
            for filename in files:
                file_path = Path(current_root) / filename
                extension = file_path.suffix.lower()

                if extension in VIDEO_EXTENSIONS and media_type in {'all', 'video'}:
                    if self._add_video(file_path):
                        results['videos'] += 1
                    else:
                        results['duplicates'] += 1

                if extension in MUSIC_EXTENSIONS and media_type in {'all', 'music'}:
                    if self._add_music(file_path):
                        results['music'] += 1
                    else:
                        results['duplicates'] += 1

        with self.database.connection() as conn:
            conn.execute(
                """
                INSERT INTO libraries (id, path, media_type, scanned_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    media_type=excluded.media_type,
                    scanned_at=excluded.scanned_at
                """,
                (
                    str(uuid.uuid4()),
                    str(root_path),
                    media_type,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return results

    def _add_video(self, file_path: Path) -> bool:
        with self.database.connection() as conn:
            existing = conn.execute(
                'SELECT id FROM videos WHERE path = ?',
                (str(file_path),),
            ).fetchone()
            if existing:
                return False

            conn.execute(
                """
                INSERT INTO videos
                (id, title, path, filename, size, duration, category, description, artwork_url, thumbnail_path, tags, added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    file_path.stem,
                    str(file_path),
                    file_path.name,
                    file_path.stat().st_size,
                    0.0,
                    'Movie',
                    None,
                    None,
                    None,
                    '',
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return True

    def _add_music(self, file_path: Path) -> bool:
        title = file_path.stem
        artist = 'Unknown Artist'
        album = 'Unknown Album'
        duration = 0.0
        genre = None

        try:
            audio = MutagenFile(file_path)
            if audio:
                duration = getattr(getattr(audio, 'info', None), 'length', 0.0) or 0.0
                tags = getattr(audio, 'tags', {}) or {}
                title = self._extract_tag(tags, ('TIT2', '\xa9nam'), title)
                artist = self._extract_tag(tags, ('TPE1', '\xa9ART'), artist)
                album = self._extract_tag(tags, ('TALB', '\xa9alb'), album)
                genre = self._extract_tag(tags, ('TCON', '\xa9gen'), '') or None
        except Exception:
            pass

        with self.database.connection() as conn:
            existing = conn.execute(
                'SELECT id FROM music WHERE path = ?',
                (str(file_path),),
            ).fetchone()
            if existing:
                return False

            conn.execute(
                """
                INSERT INTO music
                (id, title, artist, album, path, filename, size, duration, genre, category, description, artwork_url, thumbnail_path, tags, added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    title,
                    artist,
                    album,
                    str(file_path),
                    file_path.name,
                    file_path.stat().st_size,
                    duration,
                    genre,
                    'Music',
                    None,
                    None,
                    None,
                    '',
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return True

    @staticmethod
    def _extract_tag(tags: object, keys: tuple[str, ...], fallback: str) -> str:
        for key in keys:
            value = getattr(tags, 'get', lambda *_: None)(key)
            if value:
                if isinstance(value, list):
                    return str(value[0])
                if hasattr(value, 'text') and value.text:
                    return str(value.text[0])
                return str(value)
        return fallback
