from datetime import datetime, timedelta, timezone
import os
import platform
import shutil

from fastapi import APIRouter, Depends, HTTPException

try:
    import psutil
except ImportError:
    psutil = None

import hashlib
import json

from server.auth_utils import is_module_pin_lock_enabled, parse_module_pins, parse_modules, require_admin
from server.config import settings
from server.database import db
from server.schemas import AppSettingsUpdateRequest, ModulePinUpdateRequest, UserAccessUpdate

router = APIRouter(prefix='/admin', tags=['admin'], dependencies=[Depends(require_admin)])


def _normalize_modules(modules: list[str] | None) -> str | None:
    if modules is None:
        return None
    if 'all' in modules:
        return 'all'
    return ','.join(sorted(set(modules)))


@router.get('/overview')
async def admin_overview(session: dict = Depends(require_admin)) -> dict:
    now = datetime.now(timezone.utc)
    active_cutoff = (now - timedelta(hours=6)).isoformat()
    stream_cutoff = (now - timedelta(seconds=35)).isoformat()
    recent_cutoff = (now - timedelta(days=7)).isoformat()

    with db.connection() as conn:
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        active_sessions = conn.execute('SELECT COUNT(*) FROM sessions WHERE last_seen_at >= ?', (active_cutoff,)).fetchone()[0]
        all_sessions = conn.execute(
            'SELECT s.username, s.role, s.module_access, s.unlocked_modules, u.module_pins, s.ip_address, s.user_agent, s.created_at, s.last_seen_at FROM sessions s JOIN users u ON u.id = s.user_id ORDER BY s.last_seen_at DESC, s.created_at DESC LIMIT 20'
        ).fetchall()
        active_streams = conn.execute('SELECT COUNT(*) FROM active_streams WHERE last_ping_at >= ?', (stream_cutoff,)).fetchone()[0]
        active_stream_rows = conn.execute(
            'SELECT username, media_title, media_kind, device_label, started_at, last_ping_at FROM active_streams WHERE last_ping_at >= ? ORDER BY last_ping_at DESC LIMIT 20',
            (stream_cutoff,),
        ).fetchall()
        recent_stream_rows = conn.execute(
            'SELECT username, media_title, media_kind, device_label, started_at FROM stream_events ORDER BY started_at DESC LIMIT 20'
        ).fetchall()
        popular_media = conn.execute(
            """
            SELECT media_title, media_kind, COUNT(*) AS plays
            FROM stream_events
            WHERE started_at >= ?
            GROUP BY media_title, media_kind
            ORDER BY plays DESC, media_title ASC
            LIMIT 10
            """,
            (recent_cutoff,),
        ).fetchall()
        video_count = conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
        music_count = conn.execute('SELECT COUNT(*) FROM music').fetchone()[0]
        library_count = conn.execute('SELECT COUNT(*) FROM libraries').fetchone()[0]
        file_stats = conn.execute('SELECT COUNT(*) AS total_files, COALESCE(SUM(size), 0) AS total_size FROM cloud_files').fetchone()
        users_rows = conn.execute(
            'SELECT id, username, role, module_access, module_pins, created_at FROM users ORDER BY created_at ASC'
        ).fetchall()

    disk = shutil.disk_usage(settings.data_dir)
    if psutil:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_total = memory.total
        memory_used = memory.used
        memory_percent = memory.percent
    else:
        cpu_percent = None
        memory_total = None
        memory_used = None
        memory_percent = None

    sessions = []
    for row in all_sessions:
        item = dict(row)
        item['modules'] = parse_modules(item.get('module_access'))
        item['pin_enabled_modules'] = sorted(parse_module_pins(item.get('module_pins')).keys())
        sessions.append(item)

    users = []
    for row in users_rows:
        item = dict(row)
        item['modules'] = parse_modules(item.get('module_access'))
        item['pin_enabled_modules'] = sorted(parse_module_pins(item.get('module_pins')).keys())
        users.append(item)

    return {
        'current_admin': session['username'],
        'settings': {
            'module_pin_lock_enabled': is_module_pin_lock_enabled(),
        },
        'users': {
            'total': total_users,
            'admins': total_admins,
            'active_sessions': active_sessions,
            'list': users,
        },
        'streams': {
            'active': active_streams,
            'active_list': [dict(row) for row in active_stream_rows],
            'recent': [dict(row) for row in recent_stream_rows],
            'popular': [dict(row) for row in popular_media],
        },
        'libraries': library_count,
        'media': {
            'videos': video_count,
            'music': music_count,
            'files': file_stats['total_files'],
            'storage_used': file_stats['total_size'],
        },
        'system': {
            'platform': platform.platform(),
            'cpu_cores': os.cpu_count() or 1,
            'cpu_percent': cpu_percent,
            'memory_total': memory_total,
            'memory_used': memory_used,
            'memory_percent': memory_percent,
            'metrics_live': bool(psutil),
            'data_dir': str(settings.data_dir),
            'disk_total': disk.total,
            'disk_used': disk.used,
            'disk_free': disk.free,
        },
        'sessions': sessions,
    }


@router.patch('/users/{user_id}')
async def update_user_access(user_id: str, payload: UserAccessUpdate, session: dict = Depends(require_admin)) -> dict[str, str]:
    if payload.role is None and payload.modules is None:
        raise HTTPException(status_code=400, detail='No user access changes provided')

    with db.connection() as conn:
        user = conn.execute('SELECT id, username, role, module_access FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')

        is_self = user['username'] == session['username']
        next_role = payload.role or user['role']
        next_modules = _normalize_modules(payload.modules) or user['module_access']

        if is_self and next_role != 'admin':
            raise HTTPException(status_code=400, detail='You cannot remove your own admin access')

        conn.execute('UPDATE users SET role = ?, module_access = ? WHERE id = ?', (next_role, next_modules, user_id))
        conn.execute('UPDATE sessions SET role = ?, module_access = ? WHERE user_id = ?', (next_role, next_modules, user_id))

    return {'status': 'updated'}


@router.patch('/settings')
async def update_app_settings(payload: AppSettingsUpdateRequest, session: dict = Depends(require_admin)) -> dict[str, bool | str]:
    if payload.module_pin_lock_enabled is None:
        raise HTTPException(status_code=400, detail='No settings changes provided')

    db.set_setting('module_pin_lock_enabled', 'true' if payload.module_pin_lock_enabled else 'false')

    if not payload.module_pin_lock_enabled:
        with db.connection() as conn:
            conn.execute("UPDATE sessions SET unlocked_modules = ''")

    return {
        'status': 'updated',
        'module_pin_lock_enabled': payload.module_pin_lock_enabled,
    }


@router.delete('/users/{user_id}')
async def delete_user(user_id: str, session: dict = Depends(require_admin)) -> dict[str, str]:
    with db.connection() as conn:
        user = conn.execute('SELECT id, username FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        if user['username'] == session['username']:
            raise HTTPException(status_code=400, detail='You cannot delete your own account from admin page')
        conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    return {'status': 'deleted'}


@router.patch('/users/{user_id}/pin')
async def update_user_module_pin(user_id: str, payload: ModulePinUpdateRequest, session: dict = Depends(require_admin)) -> dict[str, list[str] | str]:
    with db.connection() as conn:
        user = conn.execute('SELECT id, username, module_pins FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')

        pins = parse_module_pins(user['module_pins'])
        if payload.pin is None:
            pins.pop(payload.module, None)
        else:
            pins[payload.module] = hashlib.sha256(payload.pin.encode('utf-8')).hexdigest()

        pins_json = json.dumps(pins, separators=(',', ':'))
        conn.execute('UPDATE users SET module_pins = ? WHERE id = ?', (pins_json, user_id))

        if payload.pin is not None:
            for row in conn.execute('SELECT token, unlocked_modules FROM sessions WHERE user_id = ?', (user_id,)).fetchall():
                unlocked = [module for module in (row['unlocked_modules'] or '').split(',') if module and module != payload.module]
                conn.execute('UPDATE sessions SET unlocked_modules = ? WHERE token = ?', (','.join(sorted(set(unlocked))), row['token']))

    return {'status': 'updated', 'pin_enabled_modules': sorted(pins.keys())}
