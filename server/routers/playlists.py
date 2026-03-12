import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from server.auth_utils import has_module_access, require_auth, require_music_access
from server.config import settings
from server.database import db
from server.schemas import PlaylistCreate, PlaylistItemCreate

router = APIRouter(prefix='/playlists', tags=['playlists'], dependencies=[Depends(require_music_access)])
settings.artwork_dir.mkdir(parents=True, exist_ok=True)


@router.get('')
async def list_playlists() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute('SELECT * FROM playlists ORDER BY updated_at DESC, name ASC').fetchall()
    return [dict(row) for row in rows]


@router.post('')
async def create_playlist(payload: PlaylistCreate, session: dict = Depends(require_auth)) -> dict:
    if payload.media_type in {'mixed', 'video'} and not has_module_access(session, 'video'):
        raise HTTPException(status_code=403, detail='Video access required for this playlist type')

    now = datetime.now(timezone.utc).isoformat()
    playlist_id = str(uuid.uuid4())
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO playlists (id, name, description, media_type, artwork_url, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (playlist_id, payload.name, payload.description, payload.media_type, payload.artwork_url, session['username'], now, now),
        )
        row = conn.execute('SELECT * FROM playlists WHERE id = ?', (playlist_id,)).fetchone()
    return dict(row)


@router.post('/{playlist_id}/artwork')
async def upload_playlist_artwork(playlist_id: str, file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or 'art').suffix or '.jpg'
    filename = f"playlist_{playlist_id}_{uuid.uuid4().hex}{ext}"
    destination = settings.artwork_dir / filename
    destination.write_bytes(await file.read())
    artwork_url = f'/library-art/{filename}'

    with db.connection() as conn:
        result = conn.execute(
            'UPDATE playlists SET artwork_url = ?, updated_at = ? WHERE id = ?',
            (artwork_url, datetime.now(timezone.utc).isoformat(), playlist_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail='Playlist not found')
        row = conn.execute('SELECT * FROM playlists WHERE id = ?', (playlist_id,)).fetchone()
    return dict(row)


@router.get('/{playlist_id}')
async def get_playlist(playlist_id: str) -> dict:
    with db.connection() as conn:
        playlist = conn.execute('SELECT * FROM playlists WHERE id = ?', (playlist_id,)).fetchone()
        if not playlist:
            raise HTTPException(status_code=404, detail='Playlist not found')
        rows = conn.execute(
            """
            SELECT pi.*,
                   COALESCE(v.title, m.title) AS title,
                   v.filename AS video_filename,
                   m.filename AS music_filename,
                   m.artist AS artist,
                   m.album AS album,
                   COALESCE(v.artwork_url, m.artwork_url, p.artwork_url) AS artwork_url,
                   COALESCE(v.description, m.description) AS description,
                   COALESCE(v.category, m.category) AS category,
                   COALESCE(v.duration, m.duration, 0) AS duration
            FROM playlist_items pi
            LEFT JOIN videos v ON pi.media_kind = 'video' AND pi.media_id = v.id
            LEFT JOIN music m ON pi.media_kind = 'music' AND pi.media_id = m.id
            LEFT JOIN playlists p ON pi.playlist_id = p.id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position ASC
            """,
            (playlist_id,),
        ).fetchall()
    data = dict(playlist)
    data['items'] = [dict(item) for item in rows]
    return data


@router.post('/{playlist_id}/items')
async def add_playlist_item(playlist_id: str, payload: PlaylistItemCreate, session: dict = Depends(require_auth)) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    item_id = str(uuid.uuid4())

    if payload.media_kind == 'video' and not has_module_access(session, 'video'):
        raise HTTPException(status_code=403, detail='Video access required')

    with db.connection() as conn:
        playlist = conn.execute('SELECT id FROM playlists WHERE id = ?', (playlist_id,)).fetchone()
        if not playlist:
            raise HTTPException(status_code=404, detail='Playlist not found')

        if payload.media_kind == 'video':
            media_row = conn.execute('SELECT id FROM videos WHERE id = ?', (payload.media_id,)).fetchone()
        else:
            media_row = conn.execute('SELECT id FROM music WHERE id = ?', (payload.media_id,)).fetchone()
        if not media_row:
            raise HTTPException(status_code=404, detail='Media item not found')

        next_position = conn.execute('SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_items WHERE playlist_id = ?', (playlist_id,)).fetchone()[0]
        conn.execute(
            'INSERT INTO playlist_items (id, playlist_id, media_id, media_kind, position, added_at) VALUES (?, ?, ?, ?, ?, ?)',
            (item_id, playlist_id, payload.media_id, payload.media_kind, next_position, now),
        )
        conn.execute('UPDATE playlists SET updated_at = ? WHERE id = ?', (now, playlist_id))
        row = conn.execute('SELECT * FROM playlist_items WHERE id = ?', (item_id,)).fetchone()
    return dict(row)


@router.delete('/{playlist_id}/items/{item_id}')
async def remove_playlist_item(playlist_id: str, item_id: str) -> dict[str, str]:
    now = datetime.now(timezone.utc).isoformat()
    with db.connection() as conn:
        deleted = conn.execute('DELETE FROM playlist_items WHERE id = ? AND playlist_id = ?', (item_id, playlist_id))
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail='Playlist item not found')
        conn.execute('UPDATE playlists SET updated_at = ? WHERE id = ?', (now, playlist_id))
    return {'status': 'deleted'}


@router.delete('/{playlist_id}')
async def delete_playlist(playlist_id: str) -> dict[str, str]:
    with db.connection() as conn:
        conn.execute('DELETE FROM playlist_items WHERE playlist_id = ?', (playlist_id,))
        deleted = conn.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail='Playlist not found')
    return {'status': 'deleted'}
