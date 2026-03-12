const AUTH_STORAGE_KEY = 'mediavault_auth';
let cachedPlaylists = [];
let currentVideo = null;
let currentTrack = null;
let currentPlaylist = null;
let currentStreamState = null;
let currentStreamInterval = null;
let pinModalResolver = null;
let pinModalModule = null;
const AUTOPLAY_STORAGE_KEY = 'mediavault_autoplay';
const AUDIO_VOLUME_STORAGE_KEY = 'mediavault_audio_volume';
const VIDEO_VOLUME_STORAGE_KEY = 'mediavault_video_volume';
let trackQueue = [];
let currentTrackIndex = -1;
let videoQueue = [];
let currentVideoIndex = -1;

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}
function formatDuration(seconds) {
  if (!seconds) return '--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}
function readStoredNumber(key, fallback) {
  const raw = Number(localStorage.getItem(key));
  return Number.isFinite(raw) ? raw : fallback;
}
function autoplayEnabled() { return localStorage.getItem(AUTOPLAY_STORAGE_KEY) === 'true'; }
function setAutoplayEnabled(value) { localStorage.setItem(AUTOPLAY_STORAGE_KEY, value ? 'true' : 'false'); }
function audioVolume() { return Math.min(1, Math.max(0, readStoredNumber(AUDIO_VOLUME_STORAGE_KEY, 1))); }
function videoVolume() { return Math.min(1, Math.max(0, readStoredNumber(VIDEO_VOLUME_STORAGE_KEY, 1))); }
function setAudioVolume(value) { localStorage.setItem(AUDIO_VOLUME_STORAGE_KEY, String(value)); }
function setVideoVolume(value) { localStorage.setItem(VIDEO_VOLUME_STORAGE_KEY, String(value)); }
function readAuth() { try { return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || 'null'); } catch { return null; } }
function writeAuth(data) {
  const normalized = { ...data };
  if (!Array.isArray(normalized.modules) || !normalized.modules.length) normalized.modules = ['all'];
  normalized.pin_lock_enabled = normalized.pin_lock_enabled === true;
  if (!Array.isArray(normalized.pin_enabled_modules)) normalized.pin_enabled_modules = [];
  if (!Array.isArray(normalized.unlocked_modules)) normalized.unlocked_modules = [];
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(normalized));
}
function clearAuth() { localStorage.removeItem(AUTH_STORAGE_KEY); }
function getAccessToken() { return readAuth()?.access_token || ''; }
function isLoggedIn() { const auth = readAuth(); return Boolean(auth?.access_token && auth?.username); }
function isAdmin() { return readAuth()?.role === 'admin'; }
function hasModuleAccess(module) {
  if (isAdmin()) return true;
  const modules = readAuth()?.modules || ['all'];
  return modules.includes('all') || modules.includes(module);
}
function moduleNeedsPin(module) {
  if (isAdmin()) return false;
  if (readAuth()?.pin_lock_enabled !== true) return false;
  return (readAuth()?.pin_enabled_modules || []).includes(module);
}
function isModuleUnlocked(module) {
  if (isAdmin()) return true;
  if (!moduleNeedsPin(module)) return true;
  return (readAuth()?.unlocked_modules || []).includes(module);
}
function updateUnlockedModules(unlockedModules) {
  writeAuth({ ...readAuth(), unlocked_modules: unlockedModules });
}
function routeNeedsModule(page) {
  if (['movies', 'player'].includes(page)) return 'video';
  if (['music', 'playlist'].includes(page)) return 'music';
  if (page === 'files') return 'files';
  return null;
}
async function refreshAuthFromServer() {
  if (!isLoggedIn()) return;
  try {
    const me = await apiJson('/api/auth/me');
    writeAuth({
      ...readAuth(),
      role: me.role,
      modules: me.modules || ['all'],
      pin_lock_enabled: me.pin_lock_enabled === true,
      pin_enabled_modules: me.pin_enabled_modules || [],
      unlocked_modules: me.unlocked_modules || [],
      username: me.username || readAuth()?.username,
    });
    if (me.role === 'admin') {
      closePinModal(false);
    }
  } catch {
    clearAuth();
  }
}
function authHeaders(extra = {}) { const token = getAccessToken(); return token ? { ...extra, Authorization: `Bearer ${token}` } : extra; }
async function apiFetch(url, options = {}) {
  const response = await fetch(url, { ...options, headers: authHeaders(options.headers || {}) });
  if (response.status === 401) {
    toastError('Session expired. Please login again.');
    clearAuth();
    if (document.body.dataset.page !== 'login') window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    throw new Error('Unauthorized');
  }
  return response;
}
async function apiJson(url, options = {}) {
  const response = await apiFetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
function withToken(url) { const token = getAccessToken(); return token ? `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}` : url; }
function artworkMarkup(item, fallbackText, extraClass = '') {
  const artwork = item?.artwork_url?.trim();
  return artwork
    ? `<div class="artwork-frame ${extraClass}" style="background-image:url('${artwork.replace(/'/g, "%27")}')"></div>`
    : `<div class="artwork-frame ${extraClass}">${fallbackText}</div>`;
}
function moduleCards() {
  return [
    { key: 'video', label: 'Movies', href: '/movies', icon: 'VID', tone: 'video', copy: 'Browse your video library and jump straight into playback.' },
    { key: 'music', label: 'Music', href: '/music', icon: 'AUD', tone: 'music', copy: 'Open tracks, playlists, metadata editing, and album art tools.' },
    { key: 'files', label: 'Files', href: '/files', icon: 'FIL', tone: 'files', copy: 'Manage uploads, cloud storage, downloads, and cleanup tasks.' },
    { key: 'admin', label: 'Admin', href: '/admin', icon: 'ADM', tone: 'admin', copy: 'Monitor users, sessions, streams, and live system health.' },
  ];
}
function moduleHrefToKey(href) {
  if (!href) return null;
  if (href.startsWith('/movies') || href.startsWith('/player')) return 'video';
  if (href.startsWith('/music') || href.startsWith('/playlist')) return 'music';
  if (href.startsWith('/files')) return 'files';
  return null;
}
function renderModuleLauncher(targetId, summaryId) {
  const target = document.getElementById(targetId);
  if (!target) return;

  const summary = document.getElementById(summaryId);
  const cards = moduleCards();
  const allowedCount = cards.filter((item) => item.key === 'admin' ? isAdmin() : hasModuleAccess(item.key)).length;

  if (summary) summary.textContent = `${allowedCount} app${allowedCount === 1 ? '' : 's'} available`;

  target.innerHTML = cards.map((item) => {
    const allowed = item.key === 'admin' ? isAdmin() : hasModuleAccess(item.key);
    const element = allowed ? 'a' : 'div';
    const pinLocked = allowed && item.key !== 'admin' && moduleNeedsPin(item.key) && !isModuleUnlocked(item.key);
    const attrs = allowed ? `href="${item.href}" data-module-link="true" data-module-key="${item.key}"` : 'aria-disabled="true"';
    const badge = !allowed ? 'Locked' : pinLocked ? 'PIN lock' : 'Open now';
    const footer = !allowed ? 'Access not granted' : pinLocked ? 'Unlock to open' : 'Launch app';

    return `<${element} class="module-app-card module-${item.tone}${allowed ? '' : ' locked'}" ${attrs}>
      <div class="module-app-icon">${item.icon}</div>
      <div>
        <span class="card-kicker">${allowed ? 'Available' : 'Restricted'}</span>
        <h3>${item.label}</h3>
      </div>
      <p>${item.copy}</p>
      <div class="module-app-footer">
        <span class="module-status-pill">${badge}</span>
        <span>${footer}</span>
      </div>
    </${element}>`;
  }).join('');
}
function chip(value, emptyLabel = 'Uncategorized') { return value ? `<span class="meta-chip">${value}</span>` : `<span class="meta-chip muted-chip">${emptyLabel}</span>`; }
function setLoading(targetId, message) { const target = document.getElementById(targetId); if (target) target.innerHTML = `<div class="loading-state">${message}</div>`; }
function showToast(message, tone = 'info') { const stack = document.getElementById('toast-stack'); if (!stack || !message) return; const toast = document.createElement('div'); toast.className = `toast toast-${tone}`; toast.textContent = message; stack.appendChild(toast); requestAnimationFrame(() => toast.classList.add('toast-visible')); const remove = () => { toast.classList.remove('toast-visible'); setTimeout(() => toast.remove(), 220); }; setTimeout(remove, 2600); toast.addEventListener('click', remove); }
function toastSuccess(message) { showToast(message, 'success'); }
function toastError(message) { showToast(message, 'error'); }
function toastInfo(message) { showToast(message, 'info'); }
function closePinModal(success = false) {
  const backdrop = document.getElementById('pin-modal-backdrop');
  const form = document.getElementById('pin-modal-form');
  const input = document.getElementById('pin-modal-input');
  if (backdrop) backdrop.hidden = true;
  if (form) form.reset();
  if (input) input.value = '';
  if (pinModalResolver) pinModalResolver(success);
  pinModalResolver = null;
  pinModalModule = null;
}
function bindPinModal() {
  const form = document.getElementById('pin-modal-form');
  const cancel = document.getElementById('pin-modal-cancel');
  if (form && !form.dataset.bound) {
    form.dataset.bound = 'true';
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = document.getElementById('pin-modal-input');
      const status = document.getElementById('pin-modal-status');
      const pin = input?.value?.trim() || '';
      if (!pinModalModule) return;
      if (!/^\d{4}$/.test(pin)) {
        if (status) status.textContent = 'Enter a valid 4-digit PIN.';
        return;
      }
      if (status) status.textContent = 'Unlocking module...';
      try {
        const data = await apiJson('/api/auth/unlock-module', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ module: pinModalModule, pin }),
        });
        updateUnlockedModules(data.unlocked_modules || []);
        updateAuthNav();
        if (status) status.textContent = 'Unlocked.';
        closePinModal(true);
      } catch (error) {
        if (status) status.textContent = error.message;
        toastError(error.message);
      }
    });
  }
  if (cancel && !cancel.dataset.bound) {
    cancel.dataset.bound = 'true';
    cancel.addEventListener('click', () => closePinModal(false));
  }
}
function requestModulePin(module) {
  if (!moduleNeedsPin(module) || isModuleUnlocked(module)) return Promise.resolve(true);
  bindPinModal();
  const backdrop = document.getElementById('pin-modal-backdrop');
  const title = document.getElementById('pin-modal-title');
  const copy = document.getElementById('pin-modal-copy');
  const status = document.getElementById('pin-modal-status');
  const input = document.getElementById('pin-modal-input');
  pinModalModule = module;
  if (title) title.textContent = `Unlock ${module.charAt(0).toUpperCase() + module.slice(1)}`;
  if (copy) copy.textContent = `Enter your 4-digit ${module} PIN to continue.`;
  if (status) status.textContent = 'PIN protected module.';
  if (backdrop) backdrop.hidden = false;
  setTimeout(() => input?.focus(), 0);
  return new Promise((resolve) => { pinModalResolver = resolve; });
}
async function ensureCurrentPageUnlocked() {
  const module = routeNeedsModule(document.body.dataset.page);
  if (!module || !moduleNeedsPin(module) || isModuleUnlocked(module)) return true;
  const unlocked = await requestModulePin(module);
  if (!unlocked) {
    window.location.href = '/';
    return false;
  }
  return true;
}
function bindProtectedLinks() {
  Array.from(document.querySelectorAll('a[href]')).forEach((link) => {
    if (link.dataset.pinBound) return;
    const module = link.dataset.moduleKey || moduleHrefToKey(link.getAttribute('href'));
    if (!module) return;
    link.dataset.pinBound = 'true';
    link.addEventListener('click', async (event) => {
      if (!hasModuleAccess(module) || !moduleNeedsPin(module) || isModuleUnlocked(module)) return;
      event.preventDefault();
      const unlocked = await requestModulePin(module);
      if (unlocked) window.location.href = link.getAttribute('href');
    });
  });
}
function makeStreamId() { return globalThis.crypto?.randomUUID?.() || `stream-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
async function pingStream(payload) { try { await apiJson('/api/activity/stream/ping', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); } catch {} }
async function stopStreamTracking() { if (currentStreamInterval) { clearInterval(currentStreamInterval); currentStreamInterval = null; } if (currentStreamState) { try { await apiJson('/api/activity/stream/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stream_id: currentStreamState.stream_id }) }); } catch {} currentStreamState = null; } }
function ensureStreamTracking(payload) { const sameStream = currentStreamState && currentStreamState.stream_id === payload.stream_id; currentStreamState = payload; if (!sameStream) pingStream(payload); if (currentStreamInterval) clearInterval(currentStreamInterval); currentStreamInterval = setInterval(() => { if (currentStreamState) pingStream(currentStreamState); }, 15000); }
window.addEventListener('beforeunload', () => { if (!currentStreamState) return; const payload = new Blob([JSON.stringify({ stream_id: currentStreamState.stream_id })], { type: 'application/json' }); navigator.sendBeacon('/api/activity/stream/stop?token=' + encodeURIComponent(getAccessToken()), payload); });
function updateAuthNav() {
  const loginLink = document.getElementById('auth-login-link');
  const userBox = document.getElementById('auth-user');
  const username = document.getElementById('auth-username');
  const logoutButton = document.getElementById('auth-logout-btn');
  const accountLink = document.getElementById('nav-account-link');
  const adminLink = document.getElementById('nav-admin-link');
  const moviesLink = document.getElementById('nav-movies-link');
  const musicLink = document.getElementById('nav-music-link');
  const filesLink = document.getElementById('nav-files-link');
  const dashboardMovies = document.getElementById('dashboard-open-movies');
  const dashboardMusic = document.getElementById('dashboard-open-music');
  const dashboardFiles = document.getElementById('dashboard-open-files');
  const dashboardPlaylists = document.getElementById('dashboard-open-playlists');
  const dashboardVideosSection = document.getElementById('dashboard-videos-section');
  const dashboardMusicSection = document.getElementById('dashboard-music-section');
  const auth = readAuth();

  if (isLoggedIn()) {
    if (loginLink) loginLink.hidden = true;
    if (userBox) userBox.hidden = false;
    if (username) username.textContent = auth.username;
    if (accountLink) accountLink.hidden = false;
    if (adminLink) adminLink.hidden = auth.role !== 'admin';
    if (moviesLink) moviesLink.hidden = !hasModuleAccess('video');
    if (musicLink) musicLink.hidden = !hasModuleAccess('music');
    if (filesLink) filesLink.hidden = !hasModuleAccess('files');
    if (dashboardMovies) dashboardMovies.hidden = !hasModuleAccess('video');
    if (dashboardMusic) dashboardMusic.hidden = !hasModuleAccess('music');
    if (dashboardFiles) dashboardFiles.hidden = !hasModuleAccess('files');
    if (dashboardPlaylists) dashboardPlaylists.hidden = !hasModuleAccess('music');
    if (dashboardVideosSection) dashboardVideosSection.hidden = !hasModuleAccess('video');
    if (dashboardMusicSection) dashboardMusicSection.hidden = !hasModuleAccess('music');
  } else {
    if (loginLink) loginLink.hidden = false;
    if (userBox) userBox.hidden = true;
    if (accountLink) accountLink.hidden = true;
    if (adminLink) adminLink.hidden = true;
    if (moviesLink) moviesLink.hidden = false;
    if (musicLink) musicLink.hidden = false;
    if (filesLink) filesLink.hidden = false;
    if (dashboardMovies) dashboardMovies.hidden = false;
    if (dashboardMusic) dashboardMusic.hidden = false;
    if (dashboardFiles) dashboardFiles.hidden = false;
    if (dashboardPlaylists) dashboardPlaylists.hidden = false;
    if (dashboardVideosSection) dashboardVideosSection.hidden = false;
    if (dashboardMusicSection) dashboardMusicSection.hidden = false;
  }

  if (logoutButton && !logoutButton.dataset.bound) {
    logoutButton.dataset.bound = 'true';
    logoutButton.addEventListener('click', async () => {
      try { if (isLoggedIn()) await apiFetch('/api/auth/logout', { method: 'POST' }); } catch {}
      finally { clearAuth(); window.location.href = '/login'; }
    });
  }
}
function enforceProtectedPage() {
  const page = document.body.dataset.page;
  const isProtected = document.body.dataset.protected === 'true';
  const loggedIn = isLoggedIn();

  if (isProtected && !loggedIn) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    return false;
  }
  if (page === 'admin' && loggedIn && !isAdmin()) {
    window.location.href = '/account';
    return false;
  }

  const requiredModule = routeNeedsModule(page);
  if (loggedIn && requiredModule && !hasModuleAccess(requiredModule)) {
    window.location.href = '/';
    return false;
  }

  if (page === 'login' && loggedIn) {
    window.location.href = new URLSearchParams(window.location.search).get('next') || '/';
    return false;
  }
  return true;
}
async function postAuth(url, payload) {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Authentication failed');
  return data;
}
async function uploadArtwork(url, file) {
  const formData = new FormData();
  formData.append('file', file);
  return apiJson(url, { method: 'POST', body: formData });
}
function setStatus(message, isLive) { const pill = document.getElementById('api-status'); if (!pill) return; pill.textContent = message; pill.classList.toggle('live', Boolean(isLive)); }
function renderLibraries(items, targetId = 'library-list', counterId = 'library-count') {
  const container = document.getElementById(targetId); const counter = document.getElementById(counterId); if (!container || !counter) return;
  counter.textContent = `${items.length} folder${items.length === 1 ? '' : 's'}`;
  const heroCount = document.getElementById('hero-library-count');
  const heroLastScan = document.getElementById('hero-last-scan');
  if (heroCount) heroCount.textContent = String(items.length);
  if (heroLastScan) heroLastScan.textContent = items.length ? new Date(items[0].scanned_at).toLocaleDateString() : 'Never';
  const librariesLastScan = document.getElementById('libraries-last-scan');
  if (librariesLastScan) librariesLastScan.textContent = items.length ? new Date(items[0].scanned_at).toLocaleDateString() : 'Never';
  if (!items.length) { container.innerHTML = '<p class="empty-state">Scan a media folder from the Libraries page to see it here.</p>'; return; }
  const visibleItems = items.slice(0, targetId === 'library-list' ? 4 : items.length);
  if (targetId === 'libraries-grid') {
    container.innerHTML = visibleItems.map((item) => `<article class="media-card polished-card library-grid-card"><div class="library-card-top"><div class="artwork-frame library-art">${item.media_type === 'music' ? 'AUD' : item.media_type === 'video' ? 'VID' : 'ALL'}</div><div><strong>${item.media_type.toUpperCase()} library</strong><div class="list-meta">${item.path}</div></div></div><div class="card-chip-row"><span class="meta-chip">${item.media_type}</span><span class="meta-chip muted-chip">Indexed</span></div><div class="library-card-footer"><span class="list-meta">${new Date(item.scanned_at).toLocaleString()}</span><div class="file-actions"><button class="file-action secondary compact-action" type="button" data-library-rescan="${item.id}">Rescan</button><button class="file-action danger compact-action" type="button" data-library-delete="${item.id}">Remove</button></div></div></article>`).join('');
    bindLibraryActionButtons();
    return;
  }
  container.innerHTML = visibleItems.map((item) => `<article class="library-row dashboard-library-row"><div><strong>${item.media_type.toUpperCase()} library</strong><div class="list-meta">${item.path}</div></div><div class="library-meta-group"><span class="meta-chip muted-chip">${item.media_type}</span><div class="list-meta">${new Date(item.scanned_at).toLocaleString()}</div></div></article>`).join('');
}

function bindLibraryActionButtons() {
  Array.from(document.querySelectorAll('[data-library-rescan]')).forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = 'true';
    button.addEventListener('click', async () => {
      const status = document.getElementById('library-scan-status');
      if (status) status.textContent = 'Rescanning library...';
      try {
        const result = await apiJson(`/api/libraries/${button.dataset.libraryRescan}/rescan`, { method: 'POST' });
        if (status) status.textContent = `Rescan complete: ${result.videos} videos, ${result.music} music, ${result.duplicates} duplicates.`;
        await loadLibrariesPage(true);
        await loadDashboard();
      } catch (error) {
        if (status) status.textContent = error.message;
        toastError(error.message);
      }
    });
  });
  Array.from(document.querySelectorAll('[data-library-delete]')).forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = 'true';
    button.addEventListener('click', async () => {
      const status = document.getElementById('library-scan-status');
      if (status) status.textContent = 'Removing library...';
      try {
        const result = await apiJson(`/api/libraries/${button.dataset.libraryDelete}`, { method: 'DELETE' });
        if (status) status.textContent = `Library removed: ${result.videos_removed} videos and ${result.music_removed} tracks cleaned.`; toastSuccess('Library removed successfully.');
        await loadLibrariesPage(true);
        await loadDashboard();
      } catch (error) {
        if (status) status.textContent = error.message;
        toastError(error.message);
      }
    });
  });
}
function renderVideos(items) { const c = document.getElementById('recent-videos'); if (!c) return; c.innerHTML = items.length ? items.slice(0, 4).map((item) => `<article class="media-card polished-card dashboard-video-card" data-id="${item.id}">${artworkMarkup(item, 'VID', 'card-artwork')}<strong>${item.title}</strong><div class="list-meta">${item.filename}</div><div class="card-chip-row">${chip(item.category)} ${chip(item.genre, 'No genre')}</div><p class="description-preview">${item.description || 'Open the player to add artwork and story details.'}</p><div class="movie-card-footer"><span>${formatBytes(item.size)}</span><span>Open</span></div></article>`).join('') : '<p class="empty-state">No videos found yet. Scan a library to populate this shelf.</p>'; Array.from(c.querySelectorAll('[data-id]')).forEach((card) => card.addEventListener('click', () => openMovie(card.dataset.id))); }
function renderMusic(items) { const c = document.getElementById('recent-music'); if (!c) return; c.innerHTML = items.length ? items.slice(0, 5).map((item) => `<article class="track-row polished-row dashboard-track-row" data-track-id="${item.id}">${artworkMarkup(item, 'AUD', 'small-artwork')}<div class="dashboard-track-copy"><strong>${item.title}</strong><div class="list-meta">${item.artist} - ${item.album}</div><div class="card-chip-row">${chip(item.category)} ${chip(item.genre, 'No genre')}</div></div><div class="dashboard-track-meta"><span class="list-meta">${formatDuration(item.duration || 0)}</span><span class="meta-chip muted-chip">Play</span></div></article>`).join('') : '<p class="empty-state">No tracks found yet. Scan a music folder to build your library.</p>'; Array.from(c.querySelectorAll('[data-track-id]')).forEach((row) => { const track = items.find((item) => item.id === row.dataset.trackId); row.addEventListener('click', () => playTrack(track)); }); }
function openMovie(movieId) { window.location.href = `/player?id=${encodeURIComponent(movieId)}`; }
function openPlaylist(playlistId) { window.location.href = `/playlist?id=${encodeURIComponent(playlistId)}`; }
function playlistOptionsFor(mediaKind, mediaId) { return cachedPlaylists.length ? cachedPlaylists.map((playlist) => `<button class="playlist-pill" type="button" data-playlist-id="${playlist.id}" data-media-kind="${mediaKind}" data-media-id="${mediaId}">${playlist.name}</button>`).join('') : '<p class="list-meta">Create a playlist to start adding items.</p>'; }
function bindPlaylistButtons() {
  Array.from(document.querySelectorAll('[data-playlist-id]')).forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = 'true';
    button.addEventListener('click', async () => {
      try {
        await apiJson(`/api/playlists/${button.dataset.playlistId}/items`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ media_id: button.dataset.mediaId, media_kind: button.dataset.mediaKind }) });
        const status = document.getElementById('playlist-status'); if (status) status.textContent = 'Added item to playlist.'; toastSuccess('Added to playlist.');
        await loadPlaylists();
      } catch (error) { const status = document.getElementById('playlist-status'); if (status) status.textContent = error.message; toastError(error.message); }
    });
  });
}
function renderMovieGrid(items) {
  const grid = document.getElementById('movie-grid'); const count = document.getElementById('movie-count'); const summary = document.getElementById('movie-summary'); if (!grid || !count || !summary) return;
  count.textContent = `${items.length} item${items.length === 1 ? '' : 's'}`; summary.textContent = items.length ? `${items.length} videos ready to browse` : 'No videos found';
  grid.innerHTML = items.length ? items.map((item) => `<article class="movie-card rich-card" data-id="${item.id}"><div>${artworkMarkup(item, 'VID', 'card-artwork')}<strong>${item.title}</strong><div class="list-meta">${item.filename}</div><div class="card-chip-row">${chip(item.category)} ${chip(item.genre, 'No genre')}</div><p class="description-preview">${item.description || 'No description yet. Open the player to add story notes and metadata.'}</p></div><div class="movie-card-footer"><span>${formatBytes(item.size)}</span><span>Play</span></div></article>`).join('') : '<p class="empty-state">No videos match your search.</p>';
  Array.from(grid.querySelectorAll('.movie-card')).forEach((card) => card.addEventListener('click', () => openMovie(card.dataset.id)));
}
function fillTrackEditor(track) {
  currentTrack = track;
  const status = document.getElementById('track-save-status'); if (status) status.textContent = track.title;
  const map = {
    'track-edit-title': track.title || '', 'track-edit-artist': track.artist || '', 'track-edit-album': track.album || '', 'track-edit-genre': track.genre || '', 'track-edit-category': track.category || '',
    'track-edit-year': track.year || '', 'track-edit-tags': track.tags || '', 'track-edit-description': track.description || '', 'track-edit-artwork': track.artwork_url || '',
  };
  Object.entries(map).forEach(([id, value]) => { const el = document.getElementById(id); if (el) el.value = value; });
}
function syncAutoplayControls() {
  const enabled = autoplayEnabled();
  ['audio-autoplay', 'video-autoplay'].forEach((id) => {
    const checkbox = document.getElementById(id);
    if (checkbox) checkbox.checked = enabled;
  });
}
function syncVolumeControls() {
  const audioPlayer = document.getElementById('audio-player');
  const videoPlayer = document.getElementById('video-player');
  const audioSlider = document.getElementById('audio-volume');
  const videoSlider = document.getElementById('video-volume');
  if (audioPlayer) audioPlayer.volume = audioVolume();
  if (videoPlayer) videoPlayer.volume = videoVolume();
  if (audioSlider) audioSlider.value = String(audioVolume());
  if (videoSlider) videoSlider.value = String(videoVolume());
}
function setTrackQueue(items, activeTrackId = null) {
  trackQueue = Array.isArray(items) ? items.slice() : [];
  currentTrackIndex = activeTrackId ? trackQueue.findIndex((item) => (item.media_id || item.id) === activeTrackId) : currentTrackIndex;
}
function setVideoQueue(items, activeVideoId = null) {
  videoQueue = Array.isArray(items) ? items.slice() : [];
  currentVideoIndex = activeVideoId ? videoQueue.findIndex((item) => item.id === activeVideoId) : currentVideoIndex;
}
function seekMedia(player, delta) {
  if (!player || Number.isNaN(player.duration)) return;
  player.currentTime = Math.max(0, Math.min(player.duration || 0, (player.currentTime || 0) + delta));
}
function playTrackByIndex(index) {
  if (index < 0 || index >= trackQueue.length) return;
  currentTrackIndex = index;
  playTrack(trackQueue[index], true);
}
function playNextTrack() {
  const nextIndex = currentTrackIndex + 1;
  if (nextIndex < trackQueue.length) playTrackByIndex(nextIndex);
}
function playPreviousTrack() {
  const previousIndex = currentTrackIndex - 1;
  if (previousIndex >= 0) playTrackByIndex(previousIndex);
}
function openVideoByIndex(index) {
  if (index < 0 || index >= videoQueue.length) return;
  window.location.href = `/player?id=${encodeURIComponent(videoQueue[index].id)}`;
}
function openNextVideo() {
  const nextIndex = currentVideoIndex + 1;
  if (nextIndex < videoQueue.length) openVideoByIndex(nextIndex);
}
function openPreviousVideo() {
  const previousIndex = currentVideoIndex - 1;
  if (previousIndex >= 0) openVideoByIndex(previousIndex);
}
function updateVideoControlStatus(message) {
  const status = document.getElementById('video-control-status');
  if (status) status.textContent = message;
}
function bindMediaControlEvents() {
  const audioPlayer = document.getElementById('audio-player');
  const videoPlayer = document.getElementById('video-player');
  const audioSlider = document.getElementById('audio-volume');
  const videoSlider = document.getElementById('video-volume');
  if (audioPlayer && !audioPlayer.dataset.boundControls) {
    audioPlayer.dataset.boundControls = 'true';
    audioPlayer.addEventListener('ended', () => { if (autoplayEnabled()) playNextTrack(); });
  }
  if (videoPlayer && !videoPlayer.dataset.boundControls) {
    videoPlayer.dataset.boundControls = 'true';
    videoPlayer.addEventListener('ended', () => {
      stopStreamTracking();
      if (autoplayEnabled()) openNextVideo();
    });
  }
  [['audio-previous-btn', () => playPreviousTrack()], ['audio-next-btn', () => playNextTrack()], ['audio-backward-btn', () => seekMedia(audioPlayer, -10)], ['audio-forward-btn', () => seekMedia(audioPlayer, 10)], ['video-previous-btn', () => openPreviousVideo()], ['video-next-btn', () => openNextVideo()], ['video-backward-btn', () => seekMedia(videoPlayer, -10)], ['video-forward-btn', () => seekMedia(videoPlayer, 10)]].forEach(([id, handler]) => {
    const button = document.getElementById(id);
    if (button && !button.dataset.bound) {
      button.dataset.bound = 'true';
      button.addEventListener('click', handler);
    }
  });
  [['audio-autoplay', 'change'], ['video-autoplay', 'change']].forEach(([id, eventName]) => {
    const checkbox = document.getElementById(id);
    if (checkbox && !checkbox.dataset.bound) {
      checkbox.dataset.bound = 'true';
      checkbox.addEventListener(eventName, () => {
        setAutoplayEnabled(checkbox.checked);
        syncAutoplayControls();
      });
    }
  });
  if (audioSlider && !audioSlider.dataset.bound) {
    audioSlider.dataset.bound = 'true';
    audioSlider.addEventListener('input', () => {
      const value = Number(audioSlider.value || '1');
      setAudioVolume(value);
      if (audioPlayer) audioPlayer.volume = value;
    });
  }
  if (videoSlider && !videoSlider.dataset.bound) {
    videoSlider.dataset.bound = 'true';
    videoSlider.addEventListener('input', () => {
      const value = Number(videoSlider.value || '1');
      setVideoVolume(value);
      if (videoPlayer) videoPlayer.volume = value;
    });
  }
  syncAutoplayControls();
  syncVolumeControls();
}
function playTrack(track, shouldAutoplay = true) {
  const dock = document.getElementById('audio-dock'); const player = document.getElementById('audio-player'); const title = document.getElementById('audio-title'); const subtitle = document.getElementById('audio-subtitle'); const art = document.getElementById('audio-artwork');
  if (!dock || !player || !title || !subtitle || !art) return;
  const streamId = track.media_id || track.id;
  const queueIndex = trackQueue.findIndex((item) => (item.media_id || item.id) === streamId);
  if (queueIndex >= 0) currentTrackIndex = queueIndex;
  dock.hidden = false; title.textContent = track.title; subtitle.textContent = `${track.artist} • ${track.album}`; art.style.backgroundImage = track.artwork_url ? `url('${track.artwork_url.replace(/'/g, "%27")}')` : ''; art.textContent = track.artwork_url ? '' : 'AUD';
  player.src = withToken(`/api/music/stream/${encodeURIComponent(streamId)}`); player.volume = audioVolume(); if (shouldAutoplay) player.play().catch(() => null); fillTrackEditor(track); bindMediaControlEvents();
}
function renderMusicLibrary(items) {
  const grid = document.getElementById('music-grid'); const count = document.getElementById('music-count'); const summary = document.getElementById('music-summary'); if (!grid || !count || !summary) return;
  setTrackQueue(items, currentTrack?.id || null);
  count.textContent = `${items.length} item${items.length === 1 ? '' : 's'}`; summary.textContent = items.length ? `${items.length} tracks ready to play` : 'No tracks found';
  grid.innerHTML = items.length ? items.map((item) => `<article class="music-row rich-music-row" data-id="${item.id}">${artworkMarkup(item, 'AUD', 'card-artwork small-artwork')}<div style="flex:1; min-width:0;"><strong>${item.title}</strong><div class="list-meta">${item.artist} • ${item.album}</div><div class="card-chip-row">${chip(item.category)} ${chip(item.genre, 'No genre')}</div><p class="description-preview">${item.description || 'No description yet'}</p><div class="playlist-pill-row">${playlistOptionsFor('music', item.id)}</div></div><div class="list-meta">${formatDuration(item.duration || 0)}</div></article>`).join('') : '<p class="empty-state">No tracks match your search.</p>';
  Array.from(grid.querySelectorAll('.music-row')).forEach((row) => {
    const track = items.find((item) => item.id === row.dataset.id);
    row.addEventListener('click', (event) => { if (event.target.closest('[data-playlist-id]')) return; playTrack(track); });
  });
  bindPlaylistButtons();
}
function renderFiles(items, stats) { const g = document.getElementById('files-grid'); const c = document.getElementById('files-count'); const s = document.getElementById('files-summary'); const st = document.getElementById('files-storage'); if (!g || !c || !s || !st) return; c.textContent = `${items.length} item${items.length === 1 ? '' : 's'}`; s.textContent = items.length ? `${items.length} files in cloud storage` : 'No files uploaded yet'; st.textContent = formatBytes(stats.total_size); g.innerHTML = items.length ? items.map((item) => `<article class="file-card"><div><div class="file-art">FILE</div><strong>${item.name}</strong><div class="list-meta">${item.mime_type}</div></div><div class="file-card-footer"><span>${formatBytes(item.size)}</span></div><div class="file-actions"><a class="file-action secondary" href="${withToken(`/api/files/download/${encodeURIComponent(item.id)}`)}">Download</a><button class="file-action danger" data-delete-id="${item.id}" type="button">Delete</button></div></article>`).join('') : '<p class="empty-state">No files uploaded yet.</p>'; Array.from(g.querySelectorAll('[data-delete-id]')).forEach((button) => button.addEventListener('click', async () => { await apiFetch(`/api/files/delete/${encodeURIComponent(button.dataset.deleteId)}`, { method: 'DELETE' }); await loadFilesPage(); })); }
async function loadPlaylists() {
  const list = document.getElementById('playlist-list'); const count = document.getElementById('playlist-count'); if (!list || !count) return [];
  try { cachedPlaylists = await apiJson('/api/playlists'); } catch { cachedPlaylists = []; }
  count.textContent = `${cachedPlaylists.length} item${cachedPlaylists.length === 1 ? '' : 's'}`;
  list.innerHTML = cachedPlaylists.length ? cachedPlaylists.map((playlist) => `<article class="playlist-card">${artworkMarkup(playlist, 'PL', 'small-artwork')}<div style="flex:1;"><strong>${playlist.name}</strong><div class="list-meta">${playlist.media_type} • ${playlist.description || 'No description'}</div></div><div class="file-actions"><button class="file-action secondary" type="button" data-open-playlist="${playlist.id}">Open</button><button class="file-action danger" type="button" data-delete-playlist="${playlist.id}">Delete</button></div></article>`).join('') : '<p class="empty-state">No playlists created yet.</p>';
  Array.from(document.querySelectorAll('[data-delete-playlist]')).forEach((button) => button.addEventListener('click', async () => { await apiFetch(`/api/playlists/${button.dataset.deletePlaylist}`, { method: 'DELETE' }); await loadPlaylists(); await loadMusicPage(); }));
  Array.from(document.querySelectorAll('[data-open-playlist]')).forEach((button) => button.addEventListener('click', () => openPlaylist(button.dataset.openPlaylist)));
  return cachedPlaylists;
}
async function loadDashboard() {
  const statVideos = document.getElementById('stat-videos');
  if (!statVideos) return;
  renderModuleLauncher('dashboard-module-launcher', 'dashboard-launcher-summary');
  try {
    const healthPromise = fetch('/health').then((r) => r.json());
    const videosPromise = hasModuleAccess('video') ? apiJson('/api/video/list') : Promise.resolve([]);
    const musicPromise = hasModuleAccess('music') ? apiJson('/api/music/list') : Promise.resolve([]);
    const filesPromise = hasModuleAccess('files') ? apiJson('/api/files/list') : Promise.resolve([]);
    const storagePromise = hasModuleAccess('files') ? apiJson('/api/files/stats') : Promise.resolve({ total_size: 0, file_count: 0 });

    const [health, videos, music, files, storage, libraries] = await Promise.all([
      healthPromise,
      videosPromise,
      musicPromise,
      filesPromise,
      storagePromise,
      apiJson('/api/libraries/'),
    ]);

    document.getElementById('stat-videos').textContent = videos.length;
    document.getElementById('stat-music').textContent = music.length;
    document.getElementById('stat-files').textContent = files.length;
    document.getElementById('stat-storage').textContent = formatBytes(storage.total_size);
    setStatus(`${health.status.toUpperCase()} - ${health.version}`, true);
    renderLibraries(libraries);
    renderVideos(videos);
    renderMusic(music);
  } catch {
    setStatus('Backend not reachable', false);
  }
}
async function loadLibrariesPage(forceRefresh = false) { const form = document.getElementById('library-scan-form'); if (!form) return; async function refreshPanel() { const libraries = await apiJson('/api/libraries/'); const count = document.getElementById('libraries-summary-count'); const summary = document.getElementById('libraries-summary'); if (count) count.textContent = String(libraries.length); if (summary) summary.textContent = libraries.length ? `${libraries.length} libraries indexed` : 'Ready to scan'; renderLibraries(libraries, 'libraries-grid', 'libraries-count'); }
  try { await refreshPanel(); } catch {}
  if (form.dataset.bound === 'true' && !forceRefresh) return;
  if (form.dataset.bound === 'true' && forceRefresh) return;
  form.dataset.bound = 'true';
  form.addEventListener('submit', async (event) => { event.preventDefault(); const status = document.getElementById('library-scan-status'); const payload = { folder_path: document.getElementById('library-folder')?.value?.trim() || '', media_type: document.getElementById('library-media-type')?.value || 'all' }; if (!payload.folder_path) { if (status) status.textContent = 'Please enter a folder path.'; return; } if (status) status.textContent = `Scanning ${payload.folder_path}...`; try { const result = await apiJson('/api/libraries/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); if (status) status.textContent = `Scan complete: ${result.videos} videos, ${result.music} music, ${result.duplicates} duplicates.`; toastSuccess('Library scan complete.'); await refreshPanel(); await loadDashboard(); } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } }); }
async function loadMoviesPage() { const searchInput = document.getElementById('movie-search'); if (!searchInput) return; setLoading('movie-grid', 'Loading videos...'); try { const videos = await apiJson('/api/video/list'); setVideoQueue(videos, currentVideo?.id || null); renderMovieGrid(videos); searchInput.addEventListener('input', () => { const query = searchInput.value.trim().toLowerCase(); const filtered = videos.filter((item) => `${item.title} ${item.filename} ${item.category || ''} ${item.tags || ''}`.toLowerCase().includes(query)); setVideoQueue(filtered, currentVideo?.id || null); renderMovieGrid(filtered); }); } catch { const grid = document.getElementById('movie-grid'); if (grid) grid.innerHTML = '<p class="empty-state">Could not load movies right now.</p>'; } }
async function loadMusicPage() {
  const searchInput = document.getElementById('music-search'); if (!searchInput) return; setLoading('music-grid', 'Loading tracks...'); await loadPlaylists();
  try { const tracks = await apiJson('/api/music/list'); renderMusicLibrary(tracks); bindMediaControlEvents(); searchInput.addEventListener('input', () => { const query = searchInput.value.trim().toLowerCase(); renderMusicLibrary(tracks.filter((item) => `${item.title} ${item.artist} ${item.album} ${item.category || ''} ${item.tags || ''}`.toLowerCase().includes(query))); }); } catch { const grid = document.getElementById('music-grid'); if (grid) grid.innerHTML = '<p class="empty-state">Could not load music right now.</p>'; }
  const playlistForm = document.getElementById('playlist-form'); if (playlistForm && !playlistForm.dataset.bound) { playlistForm.dataset.bound = 'true'; playlistForm.addEventListener('submit', async (event) => { event.preventDefault(); const status = document.getElementById('playlist-status'); const payload = { name: document.getElementById('playlist-name')?.value?.trim(), description: document.getElementById('playlist-description')?.value?.trim() || null, media_type: document.getElementById('playlist-type')?.value || 'mixed' }; if (!payload.name) { if (status) status.textContent = 'Playlist needs a name.'; return; } try { const playlist = await apiJson('/api/playlists', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); const file = document.getElementById('playlist-artwork-file')?.files?.[0]; if (file) await uploadArtwork(`/api/playlists/${playlist.id}/artwork`, file); if (status) status.textContent = 'Playlist created.'; toastSuccess('Playlist created.'); playlistForm.reset(); await loadPlaylists(); await loadMusicPage(); } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } }); }
  const trackForm = document.getElementById('track-metadata-form'); if (trackForm && !trackForm.dataset.bound) { trackForm.dataset.bound = 'true'; trackForm.addEventListener('submit', async (event) => { event.preventDefault(); if (!currentTrack) return; const status = document.getElementById('track-save-status'); const payload = { title: document.getElementById('track-edit-title').value.trim() || null, artist: document.getElementById('track-edit-artist').value.trim() || null, album: document.getElementById('track-edit-album').value.trim() || null, genre: document.getElementById('track-edit-genre').value.trim() || null, category: document.getElementById('track-edit-category').value.trim() || null, year: document.getElementById('track-edit-year').value ? Number(document.getElementById('track-edit-year').value) : null, tags: document.getElementById('track-edit-tags').value.trim() || null, description: document.getElementById('track-edit-description').value.trim() || null, artwork_url: document.getElementById('track-edit-artwork').value.trim() || null }; if (status) status.textContent = 'Saving...'; try { let updated = await apiJson(`/api/music/${encodeURIComponent(currentTrack.id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); const file = document.getElementById('track-artwork-file')?.files?.[0]; if (file) updated = await uploadArtwork(`/api/music/${encodeURIComponent(currentTrack.id)}/artwork`, file); fillTrackEditor(updated); if (status) status.textContent = 'Saved'; toastSuccess('Track metadata saved.'); await loadMusicPage(); } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } }); }
}
async function loadFilesPage() { const form = document.getElementById('upload-form'); if (!form) return; setLoading('files-grid', 'Loading files...'); try { const [files, stats] = await Promise.all([apiJson('/api/files/list'), apiJson('/api/files/stats')]); renderFiles(files, stats); } catch { const grid = document.getElementById('files-grid'); if (grid) grid.innerHTML = '<p class="empty-state">Could not load files right now.</p>'; }
  if (form.dataset.bound === 'true') return; form.dataset.bound = 'true'; form.addEventListener('submit', async (event) => { event.preventDefault(); const input = document.getElementById('upload-input'); const status = document.getElementById('upload-status'); const file = input?.files?.[0]; if (!file) return; const formData = new FormData(); formData.append('file', file); formData.append('folder', '/'); if (status) status.textContent = `Uploading ${file.name}...`; try { const response = await apiFetch('/api/files/upload', { method: 'POST', body: formData }); if (!response.ok) throw new Error('Upload failed'); if (status) status.textContent = `${file.name} uploaded successfully.`; toastSuccess(`${file.name} uploaded.`); form.reset(); await loadFilesPage(); await loadDashboard(); } catch { if (status) status.textContent = `Upload failed for ${file.name}.`; toastError(`Upload failed for ${file.name}.`); } }); }
function fillVideoEditor(video) { currentVideo = video; const mapText = { 'player-name': video.title, 'player-filename': video.filename, 'player-size': formatBytes(video.size), 'player-category': video.category || '-', 'player-tags': video.tags || '-', 'player-description': video.description || '-', 'player-path': video.path }; Object.entries(mapText).forEach(([id, value]) => { const el = document.getElementById(id); if (el) el.textContent = value; }); const art = document.getElementById('player-artwork'); if (art) { art.style.backgroundImage = video.artwork_url ? `url('${video.artwork_url.replace(/'/g, "%27")}')` : ''; art.textContent = video.artwork_url ? '' : 'VID'; } const editMap = { 'video-edit-title': video.title || '', 'video-edit-genre': video.genre || '', 'video-edit-category': video.category || '', 'video-edit-year': video.year || '', 'video-edit-artwork': video.artwork_url || '', 'video-edit-tags': video.tags || '', 'video-edit-description': video.description || '' }; Object.entries(editMap).forEach(([id, value]) => { const el = document.getElementById(id); if (el) el.value = value; }); }
async function loadPlayerPage() { const videoElement = document.getElementById('video-player'); if (!videoElement) return; const params = new URLSearchParams(window.location.search); const videoId = params.get('id'); if (!videoId) return; try { const [video, videos] = await Promise.all([apiJson(`/api/video/${encodeURIComponent(videoId)}`), apiJson('/api/video/list')]); setVideoQueue(videos, videoId); document.getElementById('player-title').textContent = video.title; document.getElementById('player-subtitle').textContent = 'Streaming directly from your local backend with quick seek, queue navigation, and autoplay.'; fillVideoEditor(video); videoElement.src = withToken(`/api/video/stream/${encodeURIComponent(video.id)}`); videoElement.volume = videoVolume(); updateVideoControlStatus(`${Math.max(currentVideoIndex + 1, 1)} of ${videoQueue.length || 1}`); bindMediaControlEvents(); } catch { document.getElementById('player-title').textContent = 'Could not load player'; }
  if (!videoElement.dataset.boundTracking) { videoElement.dataset.boundTracking = 'true'; videoElement.addEventListener('play', () => { if (currentVideo) ensureStreamTracking({ stream_id: videoElement.dataset.streamId || (videoElement.dataset.streamId = makeStreamId()), media_id: currentVideo.id, media_kind: 'video', media_title: currentVideo.title }); }); videoElement.addEventListener('pause', () => { if (!videoElement.ended) stopStreamTracking(); }); videoElement.addEventListener('ended', () => stopStreamTracking()); }
  videoElement.dataset.streamId = makeStreamId();
  const form = document.getElementById('video-metadata-form'); if (form && !form.dataset.bound) { form.dataset.bound = 'true'; form.addEventListener('submit', async (event) => { event.preventDefault(); if (!currentVideo) return; const status = document.getElementById('player-save-status'); const payload = { title: document.getElementById('video-edit-title').value.trim() || null, genre: document.getElementById('video-edit-genre').value.trim() || null, category: document.getElementById('video-edit-category').value.trim() || null, year: document.getElementById('video-edit-year').value ? Number(document.getElementById('video-edit-year').value) : null, artwork_url: document.getElementById('video-edit-artwork').value.trim() || null, tags: document.getElementById('video-edit-tags').value.trim() || null, description: document.getElementById('video-edit-description').value.trim() || null }; if (status) status.textContent = 'Saving...'; try { let updated = await apiJson(`/api/video/${encodeURIComponent(currentVideo.id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); const file = document.getElementById('video-artwork-file')?.files?.[0]; if (file) updated = await uploadArtwork(`/api/video/${encodeURIComponent(currentVideo.id)}/artwork`, file); fillVideoEditor(updated); document.getElementById('player-title').textContent = updated.title; if (status) status.textContent = 'Saved'; toastSuccess('Video metadata saved.'); } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } }); }
}
async function loadPlaylistPage() {
  const stage = document.getElementById('playlist-stage'); if (!stage) return; const params = new URLSearchParams(window.location.search); const playlistId = params.get('id'); if (!playlistId) return;
  try { currentPlaylist = await apiJson(`/api/playlists/${encodeURIComponent(playlistId)}`); document.getElementById('playlist-title').textContent = currentPlaylist.name; document.getElementById('playlist-subtitle').textContent = currentPlaylist.description || 'Curated playlist playback'; document.getElementById('playlist-name').textContent = currentPlaylist.name; document.getElementById('playlist-type').textContent = currentPlaylist.media_type; document.getElementById('playlist-description').textContent = currentPlaylist.description || '-'; document.getElementById('playlist-created-by').textContent = currentPlaylist.created_by; const art = document.getElementById('playlist-artwork'); if (art) { art.style.backgroundImage = currentPlaylist.artwork_url ? `url('${currentPlaylist.artwork_url.replace(/'/g, "%27")}')` : ''; art.textContent = currentPlaylist.artwork_url ? '' : 'PL'; }
    stage.innerHTML = currentPlaylist.items.length ? currentPlaylist.items.map((item) => `<article class="playlist-play-row">${artworkMarkup(item, item.media_kind === 'video' ? 'VID' : 'AUD', 'small-artwork')}<div style="flex:1;"><strong>${item.title}</strong><div class="list-meta">${item.media_kind}${item.artist ? ` • ${item.artist}` : ''}${item.album ? ` • ${item.album}` : ''}</div><p class="description-preview">${item.description || 'No description yet'}</p></div><div class="file-actions"><button class="file-action secondary" type="button" data-play-item='${JSON.stringify(item).replace(/'/g, '&apos;')}'>Play</button><button class="file-action danger" type="button" data-remove-item="${item.id}">Remove</button></div></article>`).join('') : '<p class="empty-state">This playlist has no items yet.</p>';
    Array.from(stage.querySelectorAll('[data-remove-item]')).forEach((button) => button.addEventListener('click', async () => { await apiFetch(`/api/playlists/${encodeURIComponent(playlistId)}/items/${encodeURIComponent(button.dataset.removeItem)}`, { method: 'DELETE' }); await loadPlaylistPage(); }));
    Array.from(stage.querySelectorAll('[data-play-item]')).forEach((button) => button.addEventListener('click', () => { const item = JSON.parse(button.dataset.playItem.replace(/&apos;/g, "'")); if (item.media_kind === 'video') window.location.href = `/player?id=${encodeURIComponent(item.media_id)}`; else { const queue = currentPlaylist.items.filter((entry) => entry.media_kind === 'music'); setTrackQueue(queue, item.id); playTrack(item); } }));
  } catch { stage.innerHTML = '<p class="empty-state">Could not load playlist.</p>'; }
}
function bindAuthForms() {
  const loginForm = document.getElementById('login-form'); const registerForm = document.getElementById('register-form'); if (!loginForm || !registerForm) return; const nextUrl = new URLSearchParams(window.location.search).get('next') || '/';
  loginForm.addEventListener('submit', async (event) => { event.preventDefault(); const status = document.getElementById('login-status'); const payload = Object.fromEntries(new FormData(loginForm).entries()); if (status) status.textContent = 'Logging in...'; try { const data = await postAuth('/api/auth/login', payload); writeAuth(data); updateAuthNav(); toastSuccess('Login successful.'); window.location.href = nextUrl; } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } });
  registerForm.addEventListener('submit', async (event) => { event.preventDefault(); const status = document.getElementById('register-status'); const payload = Object.fromEntries(new FormData(registerForm).entries()); if (status) status.textContent = 'Creating account...'; try { const data = await postAuth('/api/auth/register', payload); writeAuth(data); updateAuthNav(); toastSuccess('Account created.'); window.location.href = nextUrl; } catch (error) { if (status) status.textContent = error.message; toastError(error.message); } });
}

async function loadAccountPage() {
  const streamList = document.getElementById('account-streams');
  if (!streamList) return;

  renderModuleLauncher('account-module-launcher', 'account-launcher-summary');

  try {
    const data = await apiJson('/api/auth/activity');
    const role = document.getElementById('account-role');
    const summary = document.getElementById('account-summary');
    const streamCount = document.getElementById('account-stream-count');
    const sessionCount = document.getElementById('account-session-count');
    const sessionList = document.getElementById('account-sessions');

    if (role) role.textContent = data.role;
    if (summary) summary.textContent = `${data.username} - ${data.playlist_count} playlists - modules: ${(data.modules || ['all']).join(', ')}`;
    if (streamCount) streamCount.textContent = `${data.recent_streams.length} items`;
    if (sessionCount) sessionCount.textContent = `${data.sessions.length} items`;

    streamList.innerHTML = data.recent_streams.length
      ? data.recent_streams.map((item) => `<article class="library-row"><div><strong>${item.media_title || 'Unknown media'}</strong><div class="list-meta">${item.media_kind} - ${item.device_label || 'Browser'}</div></div><div class="list-meta">${new Date(item.started_at).toLocaleString()}</div></article>`).join('')
      : '<p class="empty-state">No streams yet.</p>';

    if (sessionList) {
      sessionList.innerHTML = data.sessions.length
        ? data.sessions.map((item) => `<article class="library-row"><div><strong>${item.ip_address || 'Unknown IP'}</strong><div class="list-meta">${item.user_agent || 'Unknown device'}</div></div><div class="list-meta">Last seen: ${item.last_seen_at ? new Date(item.last_seen_at).toLocaleString() : '-'}</div></article>`).join('')
        : '<p class="empty-state">No sessions found.</p>';
    }
  } catch (error) {
    streamList.innerHTML = '<p class="empty-state">Could not load your account activity.</p>';
    toastError(error.message);
  }
}

async function loadAdminPage() {
  const summary = document.getElementById('admin-summary');
  if (!summary) return;
  try {
    const data = await apiJson('/api/admin/overview');
    document.getElementById('admin-users').textContent = data.users.total;
    document.getElementById('admin-admins').textContent = data.users.admins;
    document.getElementById('admin-sessions').textContent = data.users.active_sessions;
    document.getElementById('admin-storage').textContent = formatBytes(data.media.storage_used);
    document.getElementById('admin-active-streams').textContent = data.streams.active;
    document.getElementById('admin-active-stream-count').textContent = `${data.streams.active_list.length} items`;
    document.getElementById('admin-platform').textContent = data.system.platform;
    const pinLockEnabled = data.settings?.module_pin_lock_enabled === true;
    const pinState = document.getElementById('admin-pin-setting-state');
    const pinCopy = document.getElementById('admin-pin-setting-copy');
    const pinToggle = document.getElementById('admin-toggle-pin-lock');
    if (pinState) pinState.textContent = pinLockEnabled ? 'Enabled' : 'Disabled';
    if (pinCopy) pinCopy.textContent = pinLockEnabled
      ? 'Users will be asked for module PINs where configured.'
      : 'PIN prompts are currently turned off for all users.';
    if (pinToggle) {
      pinToggle.dataset.pinLockEnabled = pinLockEnabled ? 'true' : 'false';
      pinToggle.textContent = pinLockEnabled ? 'Disable' : 'Enable';
      pinToggle.classList.toggle('danger', pinLockEnabled);
    }
    document.getElementById('admin-cpu-cores').textContent = `${data.system.cpu_cores} cores`;
    document.getElementById('admin-cpu-percent').textContent = data.system.cpu_percent == null ? 'N/A' : `${Math.round(data.system.cpu_percent)}%`;
    document.getElementById('admin-memory-percent').textContent = data.system.memory_percent == null ? 'N/A' : `${Math.round(data.system.memory_percent)}%`;
    document.getElementById('admin-cpu-note').textContent = data.system.metrics_live ? 'Live CPU load' : 'Install psutil for live CPU';
    document.getElementById('admin-memory-note').textContent = data.system.metrics_live ? `${formatBytes(data.system.memory_used)} / ${formatBytes(data.system.memory_total)}` : 'Install psutil for live RAM';
    summary.textContent = `${data.media.videos} videos, ${data.media.music} tracks, ${data.libraries} libraries`;

    document.getElementById('admin-system-list').innerHTML = [
      `<article class="library-row"><div><strong>Data directory</strong><div class="list-meta">${data.system.data_dir}</div></div></article>`,
      `<article class="library-row"><div><strong>Disk used</strong><div class="list-meta">${formatBytes(data.system.disk_used)} / ${formatBytes(data.system.disk_total)}</div></div></article>`,
      `<article class="library-row"><div><strong>Cloud files</strong><div class="list-meta">${data.media.files} files indexed</div></div></article>`,
    ].join('');

    document.getElementById('admin-session-list-count').textContent = `${data.sessions.length} items`;
    document.getElementById('admin-session-list').innerHTML = data.sessions.length
      ? data.sessions.map((item) => `<article class="library-row"><div><strong>${item.username}</strong><div class="list-meta">${item.role} - ${item.ip_address || 'Unknown IP'}</div><div class="list-meta">Modules: ${(item.modules || ['all']).join(', ')}</div></div><div class="list-meta">${item.user_agent || 'Unknown device'}</div></article>`).join('')
      : '<p class="empty-state">No sessions yet.</p>';

    document.getElementById('admin-active-stream-list').innerHTML = data.streams.active_list.length
      ? data.streams.active_list.map((item) => `<article class="library-row"><div><strong>${item.media_title || 'Unknown media'}</strong><div class="list-meta">${item.username} - ${item.device_label || item.media_kind}</div></div><div class="list-meta">Live at ${new Date(item.last_ping_at).toLocaleTimeString()}</div></article>`).join('')
      : '<p class="empty-state">No live streams right now.</p>';

    document.getElementById('admin-recent-stream-count').textContent = `${data.streams.recent.length} items`;
    document.getElementById('admin-recent-streams').innerHTML = data.streams.recent.length
      ? data.streams.recent.map((item) => `<article class="library-row"><div><strong>${item.media_title || 'Unknown media'}</strong><div class="list-meta">${item.username} - ${item.device_label || item.media_kind}</div></div><div class="list-meta">${new Date(item.started_at).toLocaleString()}</div></article>`).join('')
      : '<p class="empty-state">No streams recorded yet.</p>';

    document.getElementById('admin-popular-count').textContent = `${data.streams.popular.length} items`;
    document.getElementById('admin-popular-streams').innerHTML = data.streams.popular.length
      ? data.streams.popular.map((item) => `<article class="library-row"><div><strong>${item.media_title || 'Unknown media'}</strong><div class="list-meta">${item.media_kind}</div></div><div class="meta-chip">${item.plays} plays</div></article>`).join('')
      : '<p class="empty-state">No popular media yet.</p>';

    document.getElementById('admin-user-count').textContent = `${data.users.list.length} items`;
    const userList = document.getElementById('admin-user-list');
    userList.innerHTML = data.users.list.length
      ? data.users.list.map((item) => {
          const modules = item.modules || ['all'];
          const pinModules = item.pin_enabled_modules || [];
          const roleButton = `<button class="file-action secondary compact-action" type="button" data-user-role="${item.id}" data-next-role="${item.role === 'admin' ? 'user' : 'admin'}">${item.role === 'admin' ? 'Make User' : 'Make Admin'}</button>`;
          const deleteButton = `<button class="file-action danger compact-action" type="button" data-user-delete="${item.id}">Delete</button>`;
          const moduleButtons = ['music', 'video', 'files'].map((module) => `<button class="file-action secondary compact-action" type="button" data-user-module="${item.id}" data-module-name="${module}" data-enable="${modules.includes('all') || modules.includes(module) ? 'false' : 'true'}">${modules.includes('all') || modules.includes(module) ? `Disable ${module}` : `Enable ${module}`}</button>`).join('');
          const pinButtons = ['music', 'video', 'files'].map((module) => `<button class="file-action secondary compact-action" type="button" data-user-pin="${item.id}" data-module-name="${module}" data-has-pin="${pinModules.includes(module) ? 'true' : 'false'}">${pinModules.includes(module) ? `Clear ${module} PIN` : `Set ${module} PIN`}</button>`).join('');
          const setAllButton = `<button class="file-action secondary compact-action" type="button" data-user-module-all="${item.id}">Set All</button>`;

          return `<article class="library-row admin-user-row">
            <div class="admin-user-copy">
              <strong>${item.username}</strong>
              <div class="list-meta">${item.role} - joined ${new Date(item.created_at).toLocaleDateString()}</div>
              <div class="admin-user-chip-row">
                <span class="meta-chip">${item.role}</span>
                <span class="meta-chip muted-chip">Modules: ${modules.join(', ')}</span>
                <span class="meta-chip muted-chip">PIN: ${pinModules.length ? pinModules.join(', ') : 'none'}</span>
              </div>
            </div>
            <div class="admin-user-actions">
              ${item.username === data.current_admin ? '<span class="meta-chip">You</span>' : `
                <div class="admin-action-group">
                  <span class="admin-action-label">Role</span>
                  <div class="file-actions">${roleButton}${setAllButton}</div>
                </div>
                <div class="admin-action-group">
                  <span class="admin-action-label">Module Access</span>
                  <div class="file-actions">${moduleButtons}</div>
                </div>
                <div class="admin-action-group">
                  <span class="admin-action-label">PIN Locks</span>
                  <div class="file-actions">${pinButtons}</div>
                </div>
                <div class="admin-action-group admin-action-danger">
                  <span class="admin-action-label">Danger</span>
                  <div class="file-actions">${deleteButton}</div>
                </div>
              `}
            </div>
          </article>`;
        }).join('')
      : '<p class="empty-state">No users yet.</p>';

    Array.from(document.querySelectorAll('[data-user-role]')).forEach((button) => button.addEventListener('click', async () => {
      try {
        await apiJson(`/api/admin/users/${button.dataset.userRole}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: button.dataset.nextRole }),
        });
        toastSuccess('User role updated.');
        await loadAdminPage();
      } catch (error) {
        toastError(error.message);
      }
    }));

    Array.from(document.querySelectorAll('[data-user-module-all]')).forEach((button) => button.addEventListener('click', async () => {
      try {
        await apiJson(`/api/admin/users/${button.dataset.userModuleAll}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modules: ['all'] }),
        });
        toastSuccess('User modules set to all.');
        await loadAdminPage();
      } catch (error) {
        toastError(error.message);
      }
    }));

    Array.from(document.querySelectorAll('[data-user-module]')).forEach((button) => button.addEventListener('click', async () => {
      try {
        const user = data.users.list.find((item) => item.id === button.dataset.userModule);
        if (!user) return;
        const moduleName = button.dataset.moduleName;
        const enabled = button.dataset.enable === 'true';
        const current = new Set((user.modules || ['all']).includes('all') ? ['music', 'video', 'files'] : (user.modules || []));
        if (enabled) current.add(moduleName); else current.delete(moduleName);
        const nextModules = current.size ? Array.from(current).sort() : ['music'];

        await apiJson(`/api/admin/users/${button.dataset.userModule}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modules: nextModules }),
        });
        toastSuccess('User module access updated.');
        await loadAdminPage();
      } catch (error) {
        toastError(error.message);
      }
    }));

    Array.from(document.querySelectorAll('[data-user-pin]')).forEach((button) => button.addEventListener('click', async () => {
      try {
        const hasPin = button.dataset.hasPin === 'true';
        const moduleName = button.dataset.moduleName;
        let pin = null;
        if (!hasPin) {
          pin = window.prompt(`Set 4-digit PIN for ${moduleName}:`, '');
          if (pin == null) return;
          pin = pin.trim();
          if (!/^\d{4}$/.test(pin)) {
            toastError('PIN must be exactly 4 digits.');
            return;
          }
        }
        await apiJson(`/api/admin/users/${button.dataset.userPin}/pin`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ module: moduleName, pin }),
        });
        toastSuccess(hasPin ? 'Module PIN cleared.' : 'Module PIN saved.');
        await loadAdminPage();
      } catch (error) {
        toastError(error.message);
      }
    }));

    Array.from(document.querySelectorAll('[data-user-delete]')).forEach((button) => button.addEventListener('click', async () => {
      try {
        await apiJson(`/api/admin/users/${button.dataset.userDelete}`, { method: 'DELETE' });
        toastSuccess('User deleted.');
        await loadAdminPage();
      } catch (error) {
        toastError(error.message);
      }
    }));

    const pinToggleButton = document.getElementById('admin-toggle-pin-lock');
    if (pinToggleButton && !pinToggleButton.dataset.bound) {
      pinToggleButton.dataset.bound = 'true';
      pinToggleButton.addEventListener('click', async () => {
        try {
          const currentlyEnabled = pinToggleButton.dataset.pinLockEnabled === 'true';
          await apiJson('/api/admin/settings', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ module_pin_lock_enabled: !currentlyEnabled }),
          });
          toastSuccess(currentlyEnabled ? 'Module PIN lock disabled.' : 'Module PIN lock enabled.');
          await refreshAuthFromServer();
          await loadAdminPage();
        } catch (error) {
          toastError(error.message);
        }
      });
    }
  } catch (error) {
    summary.textContent = 'Could not load admin overview';
    toastError(error.message);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await refreshAuthFromServer();
  if (isAdmin()) {
    closePinModal(false);
  }
  if (!enforceProtectedPage()) return;
  if (!await ensureCurrentPageUnlocked()) return;
  updateAuthNav();
  bindProtectedLinks();
  bindPinModal();
  bindMediaControlEvents();
  bindAuthForms();
  loadDashboard();
  loadLibrariesPage();
  loadMoviesPage();
  loadMusicPage();
  loadFilesPage();
  loadPlayerPage();
  loadPlaylistPage();
  loadAccountPage();
  loadAdminPage();
  if (document.body.dataset.page === 'admin') setInterval(loadAdminPage, 15000);
});


















