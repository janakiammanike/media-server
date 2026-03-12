# MediaVault Pro Deployment Guide

## Scope

This guide covers:
- local Windows PC deployment
- Proxmox deployment on Ubuntu
- Proxmox deployment on Windows
- desktop manager usage
- browser/mobile access notes

## 1. Local Windows PC Deployment

### Requirements

- Python 3.12+ or 3.14
- media folders available on local disks
- optional: virtual environment

### Install

```powershell
cd "D:\apps\media server"
pip install -r requirements.txt
```

### Run the web app

```powershell
cd "D:\apps\media server"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open:
- `http://127.0.0.1:8000`
- `http://<your-pc-lan-ip>:8000`

### Run the desktop manager

```powershell
cd "D:\apps\media server"
python desktop_app.py
```

Use the desktop manager for:
- scanning libraries
- starting/stopping server
- user management
- activity monitoring
- settings and PIN lock control

## 2. Mobile Access

### Current target polish

The UI is tuned for devices around:
- 6.7 inch display
- 1080 x 2412 resolution
- 20:9 aspect ratio
- 120Hz capable screens

### Mobile access steps

1. Connect mobile and PC to the same Wi‑Fi
2. Start MediaVault Pro with:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

3. Find PC LAN IP:

```powershell
ipconfig
```

4. On mobile open:

```text
http://<PC_LAN_IP>:8000
```

### Mobile notes

- autoplay, previous/next, seek, and volume controls are available on music and movie playback pages
- sticky audio dock is optimized for narrow portrait screens
- compact cards and larger tap areas are prioritized for AMOLED/120Hz phones

## 3. Proxmox Deployment on Ubuntu VM

### Recommended VM

- Ubuntu Server 24.04 LTS
- 2 vCPU minimum
- 4 GB RAM minimum
- more storage depending on media library size

### Install Python and app

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg
mkdir -p ~/apps
cd ~/apps
git clone <your-repo-url> mediavault-pro
cd mediavault-pro
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Run once

```bash
source .venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Optional systemd service

Create:

```bash
sudo nano /etc/systemd/system/mediavault.service
```

Use:

```ini
[Unit]
Description=MediaVault Pro
After=network.target

[Service]
User=<ubuntu-user>
WorkingDirectory=/home/<ubuntu-user>/apps/mediavault-pro
Environment="MEDIAVAULT_DATA_DIR=/home/<ubuntu-user>/MediaVaultPro"
ExecStart=/home/<ubuntu-user>/apps/mediavault-pro/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mediavault
sudo systemctl start mediavault
sudo systemctl status mediavault
```

### Ubuntu GUI option inside Proxmox

If you want GUI-based use:
- install Ubuntu Desktop instead of Server
- run `python desktop_app.py`
- or expose web app through browser in the VM

For remote GUI on Ubuntu Desktop:
- use Proxmox console
- or use XRDP

## 4. Proxmox Deployment on Windows VM

### Recommended VM

- Windows 11 or Windows Server
- Python installed
- mapped media disks or SMB shares

### Install and run

```powershell
cd "D:\apps"
git clone <your-repo-url> "media server"
cd "D:\apps\media server"
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Desktop manager:

```powershell
python desktop_app.py
```

### Windows GUI option inside Proxmox

This is the easiest GUI path if you want:
- desktop manager
- folder browse dialogs
- local file explorer integration

Use Proxmox console or RDP to manage the VM.

## 5. Reverse Proxy Notes

If exposing outside LAN, use:
- Nginx Proxy Manager
- Caddy
- Nginx

Recommended path:
- keep MediaVault on `8000`
- reverse proxy on `80/443`
- add HTTPS

## 6. Media Storage Notes

- large media should stay outside repo folder
- point scans to:
  - local disks
  - mounted SMB/NFS shares
  - Proxmox passthrough disks

Recommended examples:
- Windows: `D:\Media`, `E:\Movies`, `E:\Music`
- Ubuntu: `/mnt/media/movies`, `/mnt/media/music`

## 7. Build / Release Notes

### Windows desktop EXE

```powershell
build_desktop_exe.bat
```

or:

```powershell
pyinstaller --noconfirm --clean --windowed --name MediaVaultProDesktop desktop_app.py
```

## 8. Post-Deployment Checklist

- create admin account
- scan movie/music libraries
- test movie playback controls
- test music dock controls
- test activity tab
- test mobile access from LAN
- test desktop manager user controls
- back up `.env` and database file
