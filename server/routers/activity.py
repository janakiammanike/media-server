from fastapi import APIRouter, Depends, HTTPException, Request

from server.auth_utils import has_module_access, require_auth
from server.monitoring import stop_stream, touch_stream
from server.schemas import StreamHeartbeat, StreamStopRequest

router = APIRouter(prefix='/activity', tags=['activity'], dependencies=[Depends(require_auth)])


@router.post('/stream/ping')
async def stream_ping(payload: StreamHeartbeat, request: Request, session: dict = Depends(require_auth)) -> dict[str, str]:
    if not has_module_access(session, payload.media_kind):
        raise HTTPException(status_code=403, detail=f'{payload.media_kind.title()} access required')
    touch_stream(session, request, payload.stream_id, payload.media_id, payload.media_kind, payload.media_title)
    return {'status': 'ok'}


@router.post('/stream/stop')
async def stream_stop(payload: StreamStopRequest, session: dict = Depends(require_auth)) -> dict[str, str]:
    stop_stream(payload.stream_id)
    return {'status': 'stopped'}
