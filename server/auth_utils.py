import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.database import db

bearer_scheme = HTTPBearer(auto_error=False)
MODULES = {'music', 'video', 'files'}


def _resolve_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str:
    token = request.query_params.get('token')
    if token:
        return token
    if credentials and credentials.scheme.lower() == 'bearer':
        return credentials.credentials
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing access token')


def _touch_session(token: str) -> None:
    with db.connection() as conn:
        conn.execute(
            'UPDATE sessions SET last_seen_at = ? WHERE token = ?',
            (datetime.now(timezone.utc).isoformat(), token),
        )


def parse_modules(raw_modules: str | None) -> list[str]:
    if not raw_modules:
        return ['all']
    modules = sorted({module.strip().lower() for module in raw_modules.split(',') if module.strip()})
    if not modules:
        return ['all']
    if 'all' in modules:
        return ['all']
    allowed = [module for module in modules if module in MODULES]
    return allowed or ['all']


def parse_unlocked_modules(raw_modules: str | None) -> list[str]:
    if not raw_modules:
        return []
    return sorted({module.strip().lower() for module in raw_modules.split(',') if module.strip() and module.strip().lower() in MODULES})


def parse_module_pins(raw_pins: str | None) -> dict[str, str]:
    if not raw_pins:
        return {}
    try:
        value = json.loads(raw_pins)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {key: str(pin) for key, pin in value.items() if key in MODULES and pin}


def has_module_access(session: dict[str, Any], module: str) -> bool:
    if session.get('role') == 'admin':
        return True
    modules = session.get('modules') or ['all']
    if 'all' in modules:
        return True
    return module in modules


def is_module_pin_lock_enabled() -> bool:
    return (db.get_setting('module_pin_lock_enabled', 'false') or 'false').strip().lower() == 'true'


def module_requires_pin(session: dict[str, Any], module: str) -> bool:
    if not is_module_pin_lock_enabled():
        return False
    return module in session.get('pin_enabled_modules', []) and module not in session.get('unlocked_modules', [])


def require_module_access(module: str, *, require_pin: bool = True):
    if module not in MODULES:
        raise ValueError(f'Unknown module: {module}')

    def dependency(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
        if not has_module_access(session, module):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f'{module.title()} access required')
        if require_pin and module_requires_pin(session, module):
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=f'{module.title()} PIN required')
        return session

    return dependency


def get_current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    token = _resolve_token(request, credentials)

    with db.connection() as conn:
        row = conn.execute(
            'SELECT s.token, s.user_id, s.username, s.role, s.module_access, s.unlocked_modules, u.module_pins, s.ip_address, s.user_agent, s.created_at, s.last_seen_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?',
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token')

    _touch_session(token)
    session = dict(row)
    session['token'] = token
    session['modules'] = parse_modules(session.get('module_access'))
    session['module_pins'] = parse_module_pins(session.get('module_pins'))
    session['pin_lock_enabled'] = is_module_pin_lock_enabled()
    session['pin_enabled_modules'] = sorted(session['module_pins'].keys()) if session['pin_lock_enabled'] else []
    session['unlocked_modules'] = parse_unlocked_modules(session.get('unlocked_modules'))
    return session


def require_auth(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return session


def require_admin(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    if session.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    return session


def require_music_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('music')(session)


def require_video_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('video')(session)


def require_files_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('files')(session)


def require_music_page_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('music', require_pin=False)(session)


def require_video_page_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('video', require_pin=False)(session)


def require_files_page_access(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return require_module_access('files', require_pin=False)(session)
