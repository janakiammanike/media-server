from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.auth_utils import require_auth
from server.database import db
from server.scanner import MediaScanner
from server.schemas import ScanRequest, ScanResult

router = APIRouter(dependencies=[Depends(require_auth)])
scanner = MediaScanner(db)


@router.get('/')
async def list_libraries() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute('SELECT * FROM libraries ORDER BY scanned_at DESC').fetchall()
    return [dict(row) for row in rows]


@router.post('/scan', response_model=ScanResult)
async def scan_library(payload: ScanRequest) -> ScanResult:
    try:
        result = scanner.scan_folder(payload.folder_path, payload.media_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScanResult(**result)


@router.post('/{library_id}/rescan', response_model=ScanResult)
async def rescan_library(library_id: str) -> ScanResult:
    with db.connection() as conn:
        library = conn.execute('SELECT * FROM libraries WHERE id = ?', (library_id,)).fetchone()
    if not library:
        raise HTTPException(status_code=404, detail='Library not found')

    try:
        result = scanner.scan_folder(library['path'], library['media_type'])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScanResult(**result)


@router.delete('/{library_id}')
async def delete_library(library_id: str) -> dict[str, int | str]:
    with db.connection() as conn:
        library = conn.execute('SELECT * FROM libraries WHERE id = ?', (library_id,)).fetchone()
        if not library:
            raise HTTPException(status_code=404, detail='Library not found')

        root_path = str(Path(library['path']))
        child_prefix = f"{root_path}\%"
        video_deleted = conn.execute(
            'DELETE FROM videos WHERE path = ? OR path LIKE ?',
            (root_path, child_prefix),
        ).rowcount
        music_deleted = conn.execute(
            'DELETE FROM music WHERE path = ? OR path LIKE ?',
            (root_path, child_prefix),
        ).rowcount
        conn.execute('DELETE FROM libraries WHERE id = ?', (library_id,))

    return {'status': 'deleted', 'videos_removed': video_deleted, 'music_removed': music_deleted}
