import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from server.auth_utils import require_video_access
from server.config import settings
from server.database import db
from server.schemas import MediaMetadataUpdate

router = APIRouter(dependencies=[Depends(require_video_access)])
settings.artwork_dir.mkdir(parents=True, exist_ok=True)


@router.get('/list')
async def list_videos() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute('SELECT * FROM videos ORDER BY added_at DESC').fetchall()
    return [dict(row) for row in rows]


@router.get('/search')
async def search_videos(q: str = Query(..., min_length=1)) -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute('SELECT * FROM videos WHERE title LIKE ? ORDER BY added_at DESC', (f'%{q}%',)).fetchall()
    return [dict(row) for row in rows]


@router.get('/{video_id}')
async def get_video(video_id: str) -> dict:
    with db.connection() as conn:
        row = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Video not found')
    return dict(row)


@router.patch('/{video_id}')
async def update_video(video_id: str, payload: MediaMetadataUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail='No metadata changes provided')

    allowed = {'title', 'genre', 'year', 'category', 'description', 'artwork_url', 'tags'}
    fields = [field for field in updates if field in allowed]
    if not fields:
        raise HTTPException(status_code=400, detail='No editable metadata fields provided')

    assignments = ', '.join(f"{field} = ?" for field in fields)
    values = [updates[field] for field in fields]
    values.extend([datetime.now(timezone.utc).isoformat(), video_id])

    with db.connection() as conn:
        result = conn.execute(f'UPDATE videos SET {assignments}, updated_at = ? WHERE id = ?', values)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail='Video not found')
        row = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
    return dict(row)


@router.post('/{video_id}/artwork')
async def upload_video_artwork(video_id: str, file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or 'art').suffix or '.jpg'
    filename = f"video_{video_id}_{uuid.uuid4().hex}{ext}"
    destination = settings.artwork_dir / filename
    destination.write_bytes(await file.read())
    artwork_url = f'/library-art/{filename}'

    with db.connection() as conn:
        result = conn.execute(
            'UPDATE videos SET artwork_url = ?, updated_at = ? WHERE id = ?',
            (artwork_url, datetime.now(timezone.utc).isoformat(), video_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail='Video not found')
        row = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
    return dict(row)


@router.get('/stream/{video_id}')
async def stream_video(video_id: str, request: Request) -> StreamingResponse:
    with db.connection() as conn:
        row = conn.execute('SELECT path FROM videos WHERE id = ?', (video_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Video not found')

    path = Path(row['path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='File missing on disk')

    file_size = path.stat().st_size
    range_header = request.headers.get('range')

    def iter_file(start: int, end: int):
        with path.open('rb') as file_obj:
            file_obj.seek(start)
            remaining = end - start + 1
            chunk_size = 1024 * 1024
            while remaining > 0:
                chunk = file_obj.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    if range_header:
        start_text, end_text = range_header.replace('bytes=', '').split('-')
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
        headers = {
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(end - start + 1),
            'Content-Type': 'video/mp4',
        }
        return StreamingResponse(iter_file(start, end), status_code=206, headers=headers)

    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(file_size), 'Content-Type': 'video/mp4'}
    return StreamingResponse(iter_file(0, file_size - 1), headers=headers)
