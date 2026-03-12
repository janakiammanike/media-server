import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from server.auth_utils import MODULES, is_module_pin_lock_enabled, parse_module_pins, parse_modules, require_auth
from server.database import db
from server.schemas import LoginRequest, LoginResponse, ModulePinVerifyRequest

router = APIRouter()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()


def _create_session(user_id: str, username: str, role: str, module_access: str, module_pins: str, request: Request) -> LoginResponse:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    with db.connection() as conn:
        conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        conn.execute(
            """
            INSERT INTO sessions (token, user_id, username, role, module_access, unlocked_modules, ip_address, user_agent, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                user_id,
                username,
                role,
                module_access,
                '',
                _client_ip(request),
                request.headers.get('user-agent', 'Unknown device'),
                now,
                now,
            ),
        )
    pin_lock_enabled = is_module_pin_lock_enabled()
    return LoginResponse(
        access_token=token,
        username=username,
        role=role,
        modules=parse_modules(module_access),
        pin_lock_enabled=pin_lock_enabled,
        pin_enabled_modules=sorted(parse_module_pins(module_pins).keys()) if pin_lock_enabled else [],
        unlocked_modules=[],
    )


@router.post('/register', response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: LoginRequest, request: Request) -> LoginResponse:
    user_id = str(uuid.uuid4())
    with db.connection() as conn:
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (payload.username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail='Username already exists')

        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        role = 'admin' if user_count == 0 else 'user'
        module_access = 'all'
        module_pins = '{}'
        conn.execute(
            """
            INSERT INTO users (id, username, password, role, module_access, module_pins, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload.username,
                _hash_password(payload.password),
                role,
                module_access,
                module_pins,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return _create_session(user_id, payload.username, role, module_access, module_pins, request)


@router.post('/login', response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    with db.connection() as conn:
        user = conn.execute(
            'SELECT id, username, password, role, module_access, module_pins FROM users WHERE username = ?',
            (payload.username,),
        ).fetchone()

    if not user or user['password'] != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    return _create_session(user['id'], user['username'], user['role'], user['module_access'], user['module_pins'], request)


@router.post('/logout')
async def logout(request: Request, session: dict = Depends(require_auth)) -> dict[str, str]:
    token = request.query_params.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
    with db.connection() as conn:
        conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
    return {'status': 'logged_out'}


@router.get('/me')
async def me(session: dict = Depends(require_auth)) -> dict[str, object]:
    return {
        'username': session['username'],
        'role': session['role'],
        'modules': session.get('modules', ['all']),
        'pin_lock_enabled': session.get('pin_lock_enabled', False),
        'pin_enabled_modules': session.get('pin_enabled_modules', []),
        'unlocked_modules': session.get('unlocked_modules', []),
    }


@router.get('/activity')
async def activity(session: dict = Depends(require_auth)) -> dict[str, object]:
    with db.connection() as conn:
        my_sessions = conn.execute(
            'SELECT token, ip_address, user_agent, created_at, last_seen_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC',
            (session['user_id'],),
        ).fetchall()
        recent_streams = conn.execute(
            'SELECT media_title, media_kind, device_label, started_at FROM stream_events WHERE user_id = ? ORDER BY started_at DESC LIMIT 12',
            (session['user_id'],),
        ).fetchall()
        playlist_count = conn.execute('SELECT COUNT(*) FROM playlists WHERE created_by = ?', (session['username'],)).fetchone()[0]

    return {
        'username': session['username'],
        'role': session['role'],
        'modules': session.get('modules', ['all']),
        'pin_lock_enabled': session.get('pin_lock_enabled', False),
        'pin_enabled_modules': session.get('pin_enabled_modules', []),
        'unlocked_modules': session.get('unlocked_modules', []),
        'playlist_count': playlist_count,
        'sessions': [dict(row) for row in my_sessions],
        'recent_streams': [dict(row) for row in recent_streams],
    }


@router.post('/unlock-module')
async def unlock_module(payload: ModulePinVerifyRequest, session: dict = Depends(require_auth)) -> dict[str, list[str] | str]:
    if not session.get('pin_lock_enabled'):
        raise HTTPException(status_code=400, detail='Module PIN lock is currently disabled')
    if payload.module not in MODULES:
        raise HTTPException(status_code=400, detail='Unknown module')

    pin_hash = session.get('module_pins', {}).get(payload.module)
    if not pin_hash:
        raise HTTPException(status_code=404, detail='PIN not set for this module')
    if pin_hash != _hash_pin(payload.pin):
        raise HTTPException(status_code=401, detail='Invalid PIN')

    unlocked = set(session.get('unlocked_modules', []))
    unlocked.add(payload.module)
    unlocked_modules = ','.join(sorted(unlocked))

    with db.connection() as conn:
        conn.execute('UPDATE sessions SET unlocked_modules = ? WHERE token = ?', (unlocked_modules, session['token']))

    return {'status': 'unlocked', 'unlocked_modules': sorted(unlocked)}
