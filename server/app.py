from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.config import settings
from server.routers import activity, admin, auth, files, libraries, music, playlists, video
from server.schemas import HealthResponse

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / 'web' / 'templates'
STATIC_DIR = BASE_DIR / 'web' / 'static'
settings.artwork_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version=settings.app_version)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.mount('/library-art', StaticFiles(directory=str(settings.artwork_dir)), name='library-art')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router, prefix=f'{settings.api_prefix}/auth', tags=['auth'])
app.include_router(activity.router, prefix=f'{settings.api_prefix}')
app.include_router(admin.router, prefix=f'{settings.api_prefix}')
app.include_router(video.router, prefix=f'{settings.api_prefix}/video', tags=['video'])
app.include_router(music.router, prefix=f'{settings.api_prefix}/music', tags=['music'])
app.include_router(files.router, prefix=f'{settings.api_prefix}/files', tags=['files'])
app.include_router(libraries.router, prefix=f'{settings.api_prefix}/libraries', tags=['libraries'])
app.include_router(playlists.router, prefix=f'{settings.api_prefix}')


def render_page(request: Request, template_name: str, title: str, protected: bool = True) -> HTMLResponse:
    return templates.TemplateResponse(
        template_name,
        {
            'request': request,
            'app_name': settings.app_name,
            'page_title': title,
            'protected_page': protected,
        },
    )


@app.get('/', response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return render_page(request, 'index.html', 'Dashboard')


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return render_page(request, 'login.html', 'Login', protected=False)


@app.get('/account', response_class=HTMLResponse)
async def account_page(request: Request) -> HTMLResponse:
    return render_page(request, 'account.html', 'Account')


@app.get('/admin', response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return render_page(request, 'admin.html', 'Admin')


@app.get('/libraries', response_class=HTMLResponse)
async def libraries_page(request: Request) -> HTMLResponse:
    return render_page(request, 'libraries.html', 'Libraries')


@app.get('/movies', response_class=HTMLResponse)
async def movies_page(request: Request) -> HTMLResponse:
    return render_page(request, 'movies.html', 'Movies')


@app.get('/music', response_class=HTMLResponse)
async def music_page(request: Request) -> HTMLResponse:
    return render_page(request, 'music.html', 'Music')


@app.get('/files', response_class=HTMLResponse)
async def files_page(request: Request) -> HTMLResponse:
    return render_page(request, 'files.html', 'Files')


@app.get('/playlist', response_class=HTMLResponse)
async def playlist_page(request: Request) -> HTMLResponse:
    return render_page(request, 'playlist.html', 'Playlist')


@app.get('/player', response_class=HTMLResponse)
async def player_page(request: Request) -> HTMLResponse:
    return render_page(request, 'player.html', 'Player')


@app.get('/health', response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(app=settings.app_name, version=settings.app_version)


@app.get('/favicon.ico', include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / 'favicon.svg', media_type='image/svg+xml')

