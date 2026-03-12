# MediaVault Pro

MediaVault Pro is a self-hosted media vault with both a web dashboard and a direct desktop manager.

## Final Project Status

This version is development-complete for the current milestone.

Included modules:
- FastAPI backend
- Web dashboard
- Movies library and player
- Music library and playlists
- File storage and downloads
- Auth with roles
- Admin monitoring page
- Desktop GUI manager for direct PC-based library management
- Playback controls with previous, next, seek, volume, and autoplay
- Mobile polish for 6.7 inch 1080 x 2412 portrait screens

## Desktop Manager

You can manage libraries without opening the browser.

Run:

```powershell
python desktop_app.py
```

Desktop features:
- Select a video folder and scan it
- Select a music folder and scan it
- Select a mixed media folder and scan it
- View indexed libraries
- Rescan selected library
- Remove selected library
- Start the local FastAPI server
- Stop the local FastAPI server
- Open the web dashboard when needed
- Open data, cloud, artwork, and project folders

Desktop tabs:
- `Overview`: quick counts and recent indexed libraries
- `Libraries`: scan, rescan, remove libraries
- `Users`: create users, reset passwords, change access, set module PINs
- `Activity`: active streams, recent streams, and recent sessions
- `Server`: start/stop the local server and see server output
- `Settings`: view active paths, open folders, and control module PIN lock

## Web App

Run the backend:

```powershell
python -m uvicorn main:app --reload
```

Open:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/admin`
- `http://127.0.0.1:8000/account`

## Roles

- First registered account becomes `admin`
- Later accounts become `user`

Admin can:
- View users
- Change user role
- Delete users
- See active sessions
- See recent streams
- See concurrent active streams
- View system storage snapshot
- View live CPU and RAM metrics if `psutil` is installed

User can:
- Access normal dashboard pages
- View own sessions
- View own recent streams
- Use playlists, music, movies, and files

Playback controls:
- Movies: previous, next, -10s, +10s, volume, autoplay next
- Music: previous, next, -10s, +10s, volume, autoplay next

## Live Monitoring

Tracked now:
- Recent sessions
- IP and user-agent per session
- Recent stream history
- Concurrent active streams using heartbeat
- Popular media from stream history

For full live CPU and RAM metrics, install dependencies:

```powershell
pip install -r requirements.txt
```

`psutil` is included in `requirements.txt`.

## Install

```powershell
pip install -r requirements.txt
```

Current requirements:
- fastapi
- uvicorn
- aiofiles
- jinja2
- mutagen
- python-multipart
- pydantic-settings
- psutil

## Main Entry Points

- Web backend: `main.py`
- Desktop GUI: `desktop_app.py`

## Deployment Documents

- `DEPLOYMENT_GUIDE.md`
- `GITHUB_UPLOAD_GUIDE.md`
- `PROJECT_CONTINUATION.md`

## Project Structure

- `server/`: backend app, database, routers, scanning, monitoring
- `web/templates/`: Jinja pages
- `web/static/`: JS and CSS
- `desktop_app.py`: direct desktop manager

## Recommended Daily Usage

### Only desktop library management

```powershell
python desktop_app.py
```

Use the `Libraries` tab to pick and scan folders.

### Full app usage

1. Start desktop manager
2. Start local server from the `Server` tab
3. Open web dashboard if needed
4. Use desktop manager for admin/library operations
5. Use web app for playback and media browsing

## Important Notes

- Library removal removes the indexed DB rows for files under that library path
- Media files on disk are not deleted by library removal
- Desktop manager is focused on local admin control
- Web app remains best for playback, playlists, and streaming

## Final Deliverables In This Version

Completed:
- Desktop GUI manager
- Role-based auth
- Admin and user pages
- Monitoring and stream tracking
- Mobile-polished web UI
- Toast feedback system
- Library management flows
- Documentation

## Next Possible Upgrades

Not required for this milestone, but possible later:
- Desktop media playback UI
- Thumbnail auto-generation
- User disable/ban system
- Admin charts and graphs
- Packaged `.exe` build


## EXE Build Guide

You can package the desktop manager as a Windows `.exe` using PyInstaller.

### Option 1: One-click build script

Run:

```powershell
build_desktop_exe.bat
```

This will:
- create or refresh a local virtual environment if needed
- install build dependencies
- install project requirements
- build the desktop GUI into `dist/MediaVaultProDesktop`

### Option 2: Manual build

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name MediaVaultProDesktop desktop_app.py
```

### Optional icon build

If you have an `.ico` file, place it in the project folder and run:

```powershell
pyinstaller --noconfirm --clean --windowed --name MediaVaultProDesktop --icon app.ico desktop_app.py
```

### Output location

After build completes, the executable will be here:

```text
D:/apps/media server/dist/MediaVaultProDesktop/MediaVaultProDesktop.exe
```

### Important notes

- `--windowed` hides the console and is best for the desktop GUI
- if you want a single-file build, use `--onefile`, but startup can be slower
- if Windows Defender prompts on first run, choose `More info` then `Run anyway` for your local build
- if build fails after dependency changes, delete `build/` and `dist/` and run again

### Single-file build example

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name MediaVaultProDesktop desktop_app.py
```

### Recommended final packaging flow

1. Install all dependencies
2. Test with `python desktop_app.py`
3. Build with PyInstaller
4. Open `dist/MediaVaultProDesktop`
5. Test the generated `.exe`
