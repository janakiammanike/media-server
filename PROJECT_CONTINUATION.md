# Project Continuation Guide

## Purpose

This file is for future continuation of MediaVault Pro development.

If development starts again later, begin here first.

## Current State

Project is in a stable first complete version.

Working areas:
- backend APIs
- web dashboard
- desktop manager
- auth and roles
- admin monitoring
- file upload/download
- playlists
- stream/session tracking
- desktop user management
- desktop activity tab
- movie and music playback controls
- mobile-targeted responsive polish

## Main Entry Files

- `main.py`
- `desktop_app.py`
- `server/app.py`
- `server/database.py`
- `server/routers/admin.py`
- `web/static/app.js`
- `web/static/style.css`

## Where To Continue Next

### Highest-value next tasks
1. thumbnail and poster generation
2. admin graphs and analytics
3. user disable or ban actions
4. stream force-stop action from admin
5. desktop playback support
6. `.exe` packaging refinement
7. production auth hardening if internet-exposed

## Safe Restart Steps

### Web app
```powershell
cd "D:\apps\media server"
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### Desktop app
```powershell
cd "D:\apps\media server"
python desktop_app.py
```

## Database Notes

SQLite file location is controlled by:
- `server/config.py`
- `settings.db_path`

Main DB entities:
- users
- sessions
- libraries
- videos
- music
- cloud_files
- playlists
- playlist_items
- stream_events
- active_streams

## Role Logic

- first user becomes `admin`
- other users become `user`
- admin page is protected
- account page is for normal personal activity view

## Monitoring Logic

### Recent streams
Saved in:
- `stream_events`

### Concurrent streams
Saved in:
- `active_streams`

Frontend sends heartbeat while media plays.

## Playback Status

Implemented:
- music previous / next
- movie previous / next
- forward 10s / backward 10s
- autoplay next toggle
- volume sliders for audio and video

Main files:
- `web/templates/player.html`
- `web/templates/music.html`
- `web/static/app.js`
- `web/static/style.css`

## Mobile Polish Notes

Current responsive target used during polish:
- 6.7 inch AMOLED class phones
- 1080 x 2412
- 20:9 aspect ratio

UI tuning focused on:
- larger touch targets
- compact cards
- sticky dock spacing
- better playback controls on narrow portrait screens

## Frontend Notes

Main browser logic lives in:
- `web/static/app.js`

Main styles live in:
- `web/static/style.css`

If UI changes are needed, these two files are the primary place to continue.

## Desktop Manager Notes

Desktop manager is intentionally simple and local-first.

Key behaviors:
- scans folders directly using backend scanner code
- reads from same SQLite database
- can run local server
- does not require browser for library management

## Before Starting New Features

Check these first:
- `README.md`
- `DEVELOPMENT_V1.md`
- `MOBILE_ACCESS_GUIDE.md`
- `DEPLOYMENT_GUIDE.md`
- `GITHUB_UPLOAD_GUIDE.md`
- `desktop_app.py`

## Suggested Future Documentation Pattern

If new milestone starts, create:
- `DEVELOPMENT_V2.md`
- `CHANGELOG_V2.md`
- `DEPLOYMENT_GUIDE.md` if deployment becomes bigger
