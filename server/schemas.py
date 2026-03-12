from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = 'ok'
    app: str
    version: str


class ScanRequest(BaseModel):
    folder_path: str = Field(..., min_length=1)
    media_type: str = Field(default='all', pattern='^(all|video|music)$')


class ScanResult(BaseModel):
    videos: int = 0
    music: int = 0
    duplicates: int = 0


class MetadataMixin(BaseModel):
    category: str | None = None
    description: str | None = None
    artwork_url: str | None = None
    thumbnail_path: str | None = None
    tags: str | None = None
    updated_at: datetime | str | None = None


class VideoItem(MetadataMixin):
    id: str
    title: str
    path: str
    filename: str
    size: int
    duration: float
    year: int | None = None
    genre: str | None = None
    added_at: datetime | str


class MusicItem(MetadataMixin):
    id: str
    title: str
    artist: str
    album: str
    path: str
    filename: str
    size: int
    duration: float
    genre: str | None = None
    year: int | None = None
    added_at: datetime | str


class CloudFileItem(BaseModel):
    id: str
    name: str
    path: str
    size: int
    mime_type: str
    folder: str
    uploaded_at: datetime | str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    username: str
    role: str = 'user'
    modules: list[str] = Field(default_factory=lambda: ['all'])
    pin_lock_enabled: bool = False
    pin_enabled_modules: list[str] = Field(default_factory=list)
    unlocked_modules: list[str] = Field(default_factory=list)


class MediaMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    genre: str | None = None
    year: int | None = None
    category: str | None = None
    description: str | None = None
    artwork_url: str | None = None
    tags: str | None = None


class MusicMetadataUpdate(MediaMetadataUpdate):
    artist: str | None = None
    album: str | None = None


class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    media_type: str = Field(default='mixed', pattern='^(mixed|video|music)$')
    artwork_url: str | None = None


class PlaylistItemCreate(BaseModel):
    media_id: str = Field(..., min_length=1)
    media_kind: str = Field(..., pattern='^(video|music)$')


class PlaylistItem(BaseModel):
    id: str
    playlist_id: str
    media_id: str
    media_kind: str
    position: int
    added_at: datetime | str


class Playlist(BaseModel):
    id: str
    name: str
    description: str | None = None
    media_type: str
    artwork_url: str | None = None
    created_by: str
    created_at: datetime | str
    updated_at: datetime | str


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern='^(admin|user)$')


class UserAccessUpdate(BaseModel):
    role: str | None = Field(default=None, pattern='^(admin|user)$')
    modules: list[str] | None = None

    @field_validator('modules')
    @classmethod
    def validate_modules(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        normalized = sorted({module.strip().lower() for module in value if module and module.strip()})
        if not normalized:
            raise ValueError('At least one module is required')

        allowed = {'all', 'music', 'video', 'files'}
        invalid = [module for module in normalized if module not in allowed]
        if invalid:
            raise ValueError(f'Invalid modules: {", ".join(invalid)}')

        if 'all' in normalized and len(normalized) > 1:
            raise ValueError('Use only "all" or specific modules')

        return normalized


class ModulePinVerifyRequest(BaseModel):
    module: str = Field(..., pattern='^(music|video|files)$')
    pin: str = Field(..., min_length=4, max_length=4)


class ModulePinUpdateRequest(BaseModel):
    module: str = Field(..., pattern='^(music|video|files)$')
    pin: str | None = Field(default=None, min_length=4, max_length=4)


class AppSettingsUpdateRequest(BaseModel):
    module_pin_lock_enabled: bool | None = None


class StreamHeartbeat(BaseModel):
    stream_id: str = Field(..., min_length=1)
    media_id: str = Field(..., min_length=1)
    media_kind: str = Field(..., pattern='^(video|music)$')
    media_title: str = Field(..., min_length=1)


class StreamStopRequest(BaseModel):
    stream_id: str = Field(..., min_length=1)
