# First Version Development Documentation

## Project Name

MediaVault Pro

## Goal Of This Version

Build a first complete working version of MediaVault Pro with:
- self-hosted media management
- browser-based playback
- admin and user roles
- file storage
- playlist support
- direct desktop manager for library scanning

## What Was Built

### Backend
- FastAPI app structure
- SQLite database
- auth system
- session token validation
- admin-protected APIs
- library scanning
- video APIs
- music APIs
- files APIs
- playlists APIs
- activity and monitoring APIs

### Web UI
- login and register
- dashboard
- libraries management page
- movies page
- player page
- music page
- playlist page
- files page
- account page
- admin page
- toast messages
- mobile polish
- movie playback controls
- music playback controls
- autoplay, volume, previous, next, forward, backward

### Desktop GUI
- direct PC desktop manager using `tkinter`
- scan video folder
- scan music folder
- scan mixed folder
- rescan selected library
- remove selected library
- start and stop local server
- open dashboard when needed
- user management tab
- activity and streams tab
- PIN lock setting

## Architecture Summary

### Backend stack
- Python
- FastAPI
- SQLite
- Jinja2
- Mutagen
- Uvicorn

### Frontend stack
- Jinja templates
- vanilla JavaScript
- CSS

### Desktop stack
- Python `tkinter`

## Main Functional Flow

1. User creates account
2. First account becomes admin
3. Admin scans media folders
4. Media gets indexed into database
5. Users browse movies/music/files
6. Streams are tracked
7. Admin can monitor users, sessions, and streams

## Important Design Decisions

- Used SQLite for first version simplicity
- Used Jinja + vanilla JS to keep deployment easy
- Used `tkinter` for desktop GUI to avoid heavy extra dependencies
- Used token-based auth for protected APIs
- Used heartbeat-based active stream tracking for admin visibility

## Development Completion Status

This first version is considered development-complete for milestone 1.

Completed in milestone 1:
- backend core
- frontend core
- desktop manager
- admin/user roles
- monitoring foundation
- documentation
- playback controls
- mobile playback polish
- deployment documentation

## Known Limitations

- no automatic thumbnail generation yet
- no desktop playback UI yet
- no ban/disable user system yet
- live CPU/RAM metrics depend on `psutil`
- admin charts/graphs not added yet
- `.exe` package is documented but must be built locally

## Recommended Next Milestones

### Milestone 2
- thumbnail/poster generation
- richer admin charts
- stream force-stop from admin
- disable/ban user actions

### Milestone 3
- packaged installer
- desktop playback controls
- advanced search/filtering
- backup/export tools
