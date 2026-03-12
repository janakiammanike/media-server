# Mobile Access Guide

## Goal

Use MediaVault Pro from a mobile phone on the same network.

## Important Condition

Phone and PC must be connected to the same Wi-Fi network.

## Step 1: Start The Server On PC

```powershell
cd "D:\apps\media server"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Why `0.0.0.0`:
- this allows access from other devices on the same network
- `127.0.0.1` only works on the same PC

## Step 2: Find Your PC Local IP Address

Run on PC:

```powershell
ipconfig
```

Look for:
- `IPv4 Address`

Example:
- `192.168.1.23`

## Step 3: Open On Mobile

On your phone browser open:

```text
http://192.168.1.23:8000
```

Replace `192.168.1.23` with your PC local IP.

## Main Mobile URLs

- Dashboard: `http://YOUR-IP:8000/`
- Login: `http://YOUR-IP:8000/login`
- Movies: `http://YOUR-IP:8000/movies`
- Music: `http://YOUR-IP:8000/music`
- Files: `http://YOUR-IP:8000/files`
- Admin: `http://YOUR-IP:8000/admin`

## If Mobile Cannot Open The App

Check these one by one:

### 1. Same Wi-Fi
- phone and PC must be on same network

### 2. Correct host binding
- server must run with `--host 0.0.0.0`

### 3. Correct IP address
- use PC local IPv4 address, not `127.0.0.1`

### 4. Windows Firewall
- allow Python or port `8000` when prompted
- if firewall blocks, mobile device cannot connect

### 5. Server still running
- keep terminal open while using mobile

## Recommended Mobile Usage

Good for mobile:
- browse dashboard
- play movies
- play music
- access files
- basic admin checks

Better on desktop:
- full library scanning
- bulk management
- desktop GUI manager tasks

## Security Notes

Current mobile access is intended mainly for local network use.

For internet/public access, you should later add:
- reverse proxy
- HTTPS
- secure domain
- stronger deployment rules

## Best Daily Mobile Setup

1. Start server on PC with `0.0.0.0`
2. Find local IP with `ipconfig`
3. Open `http://YOUR-IP:8000` on mobile
4. Login with your account
5. Use dashboard, movies, music, and files
