from datetime import datetime, timezone
import uuid

from fastapi import Request

from server.database import db


def client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


def device_label(user_agent: str) -> str:
    lowered = user_agent.lower()
    if 'android' in lowered:
        return 'Android'
    if 'iphone' in lowered or 'ipad' in lowered or 'ios' in lowered:
        return 'iPhone/iPad'
    if 'windows' in lowered:
        return 'Windows'
    if 'macintosh' in lowered or 'mac os' in lowered:
        return 'Mac'
    if 'linux' in lowered:
        return 'Linux'
    return 'Browser'


def touch_stream(session: dict, request: Request, stream_id: str, media_id: str, media_kind: str, media_title: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    user_agent = request.headers.get('user-agent', 'Unknown device')
    ip_address = client_ip(request)
    device = device_label(user_agent)

    with db.connection() as conn:
        existing = conn.execute('SELECT stream_id FROM active_streams WHERE stream_id = ?', (stream_id,)).fetchone()
        if existing:
            conn.execute(
                '''
                UPDATE active_streams
                SET media_id = ?, media_kind = ?, media_title = ?, device_label = ?, user_agent = ?, ip_address = ?, last_ping_at = ?
                WHERE stream_id = ?
                ''',
                (media_id, media_kind, media_title, device, user_agent, ip_address, now, stream_id),
            )
            return

        conn.execute(
            '''
            INSERT INTO active_streams (stream_id, user_id, username, media_id, media_kind, media_title, device_label, user_agent, ip_address, started_at, last_ping_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (stream_id, session['user_id'], session['username'], media_id, media_kind, media_title, device, user_agent, ip_address, now, now),
        )
        conn.execute(
            '''
            INSERT INTO stream_events (id, user_id, username, media_id, media_kind, media_title, device_label, user_agent, ip_address, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (str(uuid.uuid4()), session['user_id'], session['username'], media_id, media_kind, media_title, device, user_agent, ip_address, now),
        )


def stop_stream(stream_id: str) -> None:
    with db.connection() as conn:
        conn.execute('DELETE FROM active_streams WHERE stream_id = ?', (stream_id,))
