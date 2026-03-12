# GitHub Upload Guide

## 1. Prepare the project

Open PowerShell:

```powershell
cd "D:\apps\media server"
git init
git status
```

## 2. Create `.gitignore`

Make sure these are ignored:

```gitignore
.venv/
__pycache__/
*.pyc
dist/
build/
MediaVaultProDesktop.spec
.env
*.db
```

If the file does not exist yet, create it before commit.

## 3. First commit

```powershell
git add .
git commit -m "Initial MediaVault Pro release"
```

## 4. Create GitHub repo

On GitHub:
- click `New repository`
- name it `mediavault-pro`
- choose public or private
- do not add README if repo already has files locally

## 5. Connect local repo to GitHub

```powershell
git remote add origin https://github.com/<your-username>/mediavault-pro.git
git branch -M main
git push -u origin main
```

## 6. Recommended files to keep in repo

- `server/`
- `web/`
- `desktop_app.py`
- `main.py`
- `README.md`
- `DEVELOPMENT_V1.md`
- `PROJECT_CONTINUATION.md`
- `DEPLOYMENT_GUIDE.md`
- `MOBILE_ACCESS_GUIDE.md`
- `GITHUB_UPLOAD_GUIDE.md`

## 7. Recommended files not to upload

- `.env`
- actual SQLite database
- personal media folders
- generated `dist/` and `build/`
- personal test data

## 8. Release flow for future updates

```powershell
git status
git add .
git commit -m "Add playback controls and mobile polish"
git push
```

## 9. Suggested GitHub repo sections

### Repository description

`Self-hosted media server with FastAPI web UI and desktop manager`

### Suggested topics

- `python`
- `fastapi`
- `media-server`
- `self-hosted`
- `sqlite`
- `tkinter`
- `jinja2`

## 10. Suggested release tags

- `v1.0.0` first stable milestone
- `v1.1.0` playback and mobile polish
- `v1.2.0` deployment and admin enhancements
