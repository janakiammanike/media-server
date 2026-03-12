import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from server.auth_utils import require_music_access
from server.config import settings
from server.database import db
from server.schemas import MusicMetadataUpdate

router = APIRouter(dependencies=[Depends(require_music_access)])
settings.artwork_dir.mkdir(parents=True, exist_ok=True)

MIME_TYPES = {
    '.mp3': 'audio/mpeg',
    '.flac': 'audio/flac',
    '.wav': 'audio/wav',
    '.ogg': 'audio/ogg',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
}


@router.get('/list')
async def list_music() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute('SELECT * FROM music ORDER BY artist, album, title').fetchall()
    return [dict(row) for row in rows]


@router.get('/artists')
async def list_artists() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute("SELECT artist, COUNT(*) AS track_count FROM music GROUP BY artist ORDER BY artist").fetchall()
    return [dict(row) for row in rows]


@router.get('/albums')
async def list_albums() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute("SELECT album, artist, COUNT(*) AS track_count FROM music GROUP BY album, artist ORDER BY artist, album").fetchall()
    return [dict(row) for row in rows]


@router.get('/search')
async def search_music(q: str = Query(..., min_length=1)) -> list[dict]:
    pattern = f'%{q}%'
    with db.connection() as conn:
        rows = conn.execute(
            'SELECT * FROM music WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? ORDER BY artist, album, title',
            (pattern, pattern, pattern),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get('/{music_id}')
async def get_track(music_id: str) -> dict:
    with db.connection() as conn:
        row = conn.execute('SELECT * FROM music WHERE id = ?', (music_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Track not found')
    return dict(row)


@router.patch('/{music_id}')
async def update_track(music_id: str, payload: MusicMetadataUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail='No metadata changes provided')

    allowed = {'title', 'artist', 'album', 'genre', 'year', 'category', 'description', 'artwork_url', 'tags'}
    fields = [field for field in updates if field in allowed]
    if not fields:
        raise HTTPException(status_code=400, detail='No editable metadata fields provided')

    assignments = ', '.join(f"{field} = ?" for field in fields)
    values = [updates[field] for field in fields]
    values.extend([datetime.now(timezone.utc).isoformat(), music_id])

    with db.connection() as conn:
        result = conn.execute(f'UPDATE music SET {assignments}, updated_at = ? WHERE id = ?', values)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail='Track not found')
        row = conn.execute('SELECT * FROM music WHERE id = ?', (music_id,)).fetchone()
    return dict(row)


@router.post('/{music_id}/artwork')
async def upload_track_artwork(music_id: str, file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or 'art').suffix or '.jpg'
    filename = f"music_{music_id}_{uuid.uuid4().hex}{ext}"
    destination = settings.artwork_dir / filename
    destination.write_bytes(await file.read())
    artwork_url = f'/library-art/{filename}'

    with db.connection() as conn:
        result = conn.execute(
            'UPDATE music SET artwork_url = ?, updated_at = ? WHERE id = ?',
            (artwork_url, datetime.now(timezone.utc).isoformat(), music_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail='Track not found')
        row = conn.execute('SELECT * FROM music WHERE id = ?', (music_id,)).fetchone()
    return dict(row)


@router.get('/stream/{music_id}')
async def stream_music(music_id: str, request: Request) -> StreamingResponse:
    with db.connection() as conn:
        row = conn.execute('SELECT path FROM music WHERE id = ?', (music_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Track not found')

    path = Path(row['path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='File missing on disk')

    def iter_file():
        with path.open('rb') as file_obj:
            while chunk := file_obj.read(1024 * 1024):
                yield chunk

    return StreamingResponse(iter_file(), media_type=MIME_TYPES.get(path.suffix.lower(), 'audio/mpeg'))
