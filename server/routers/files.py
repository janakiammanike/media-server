import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from server.auth_utils import require_files_access
from server.config import settings
from server.database import db

router = APIRouter(dependencies=[Depends(require_files_access)])
settings.cloud_dir.mkdir(parents=True, exist_ok=True)


@router.get('/list')
async def list_files(folder: str = '/') -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            'SELECT * FROM cloud_files WHERE folder = ? ORDER BY uploaded_at DESC, name ASC',
            (folder,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post('/upload')
async def upload_file(file: UploadFile = File(...), folder: str = Form('/')) -> dict:
    file_id = str(uuid.uuid4())
    safe_name = Path(file.filename or 'upload.bin').name
    stored_name = f'{file_id}_{safe_name}'
    destination = settings.cloud_dir / stored_name

    contents = await file.read()
    destination.write_bytes(contents)
    mime_type = mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'
    size = destination.stat().st_size

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO cloud_files (id, name, path, size, mime_type, folder, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, safe_name, str(destination), size, mime_type, folder, datetime.now(timezone.utc).isoformat()),
        )

    return {'id': file_id, 'name': safe_name, 'size': size, 'mime_type': mime_type}


@router.get('/download/{file_id}')
async def download_file(file_id: str) -> FileResponse:
    with db.connection() as conn:
        row = conn.execute(
            'SELECT name, path FROM cloud_files WHERE id = ?',
            (file_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail='File not found')

    path = Path(row['path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='Stored file missing on disk')

    return FileResponse(path, filename=row['name'])


@router.delete('/delete/{file_id}')
async def delete_file(file_id: str) -> dict[str, str]:
    with db.connection() as conn:
        row = conn.execute(
            'SELECT path FROM cloud_files WHERE id = ?',
            (file_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='File not found')

        conn.execute('DELETE FROM cloud_files WHERE id = ?', (file_id,))

    path = Path(row['path'])
    if path.exists():
        path.unlink()

    return {'status': 'deleted'}


@router.get('/stats')
async def storage_stats() -> dict[str, int]:
    with db.connection() as conn:
        total_size = conn.execute('SELECT COALESCE(SUM(size), 0) FROM cloud_files').fetchone()[0]
        file_count = conn.execute('SELECT COUNT(*) FROM cloud_files').fetchone()[0]
    return {'total_size': total_size, 'file_count': file_count}
