const content = document.getElementById('content');
const breadcrumbs = document.getElementById('breadcrumbs');
const searchInput = document.getElementById('search-input');
const audio = document.getElementById('audio');
const nowCover = document.getElementById('now-cover');
const nowTitle = document.getElementById('now-title');
const nowArtist = document.getElementById('now-artist');
const nowStats = document.getElementById('now-stats');
const uploadBtn = document.getElementById('upload-btn');
const uploadInput = document.getElementById('upload-input');
const uploadStatus = document.getElementById('upload-status');
const recentBtn = document.getElementById('recent-btn');
const playlistsBtn = document.getElementById('playlists-btn');
const loopBtn = document.getElementById('loop-btn');
const lyricsBtn = document.getElementById('lyrics-btn');
const lyricsSidebar = document.getElementById('lyrics-sidebar');
const lyricsTrackTitle = document.getElementById('lyrics-track-title');
const lyricsContent = document.getElementById('lyrics-content');
const lyricsCloseBtn = document.getElementById('lyrics-close-btn');

let apiKey = localStorage.getItem('apiKey');
const coverCache = new Map();

// --- Loop / repeat ---
// Cycles off -> all -> one -> off. 'one' is delegated to the native <audio loop>
// so a single track repeats without our 'ended' handler needing to do anything;
// 'all' wraps the queue back to index 0 once the last track ends.
let loopMode = 'off';

function updateLoopUI() {
  const labels = { off: 'Repeat: Off', all: 'Repeat: All', one: 'Repeat: One' };
  loopBtn.title = labels[loopMode];
  loopBtn.classList.toggle('active', loopMode !== 'off');
  document.getElementById('loop-badge').classList.toggle('hidden', loopMode !== 'one');
  audio.loop = loopMode === 'one';
}

loopBtn.addEventListener('click', () => {
  loopMode = loopMode === 'off' ? 'all' : loopMode === 'all' ? 'one' : 'off';
  updateLoopUI();
});

// --- Lyrics ---
// Reads whatever is embedded in the FLAC file's own 'lyrics' tag (see app/tags.py) —
// this never fetches from any external source, only what's already in the file. If
// that text is in LRC format ([mm:ss.xx] per line), synced highlighting/auto-scroll
// tracks it against audio.currentTime; otherwise it's shown as plain unsynced text.

let lrcLines = []; // [{time, text}], sorted by time; empty when unsynced or no lyrics

function parseLrc(text) {
  const timeTag = /\[(\d+):(\d+(?:\.\d+)?)\]/g;
  const lines = [];
  let sawTimestamp = false;

  for (const rawLine of text.split('\n')) {
    const matches = [...rawLine.matchAll(timeTag)];
    if (matches.length === 0) continue;
    sawTimestamp = true;
    const lineText = rawLine.replace(timeTag, '').trim();
    for (const m of matches) {
      lines.push({ time: parseInt(m[1], 10) * 60 + parseFloat(m[2]), text: lineText });
    }
  }

  if (!sawTimestamp) return null;
  lines.sort((a, b) => a.time - b.time);
  return lines;
}

function renderLyricsText(lyrics) {
  lrcLines = [];
  const parsed = parseLrc(lyrics);

  if (!parsed) {
    lyricsContent.textContent = lyrics;
    return;
  }

  lrcLines = parsed;
  lyricsContent.innerHTML = '';
  parsed.forEach((line, i) => {
    const div = document.createElement('div');
    div.className = 'lyric-line';
    div.dataset.index = i;
    div.textContent = line.text;
    lyricsContent.appendChild(div);
  });
}

audio.addEventListener('play', () => nowCover.classList.add('spinning'));
audio.addEventListener('pause', () => nowCover.classList.remove('spinning'));

audio.addEventListener('timeupdate', () => {
  if (!lrcLines.length || !lyricsSidebar.classList.contains('open')) return;
  const t = audio.currentTime;
  let activeIdx = -1;
  for (let i = 0; i < lrcLines.length; i++) {
    if (lrcLines[i].time <= t) activeIdx = i;
    else break;
  }
  lyricsContent.querySelectorAll('.lyric-line').forEach((el) => {
    el.classList.toggle('active', Number(el.dataset.index) === activeIdx);
  });
  if (activeIdx >= 0) {
    lyricsContent
      .querySelector(`.lyric-line[data-index="${activeIdx}"]`)
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
});

async function openLyrics() {
  const track = queue[queueIndex];
  if (!track) return;

  lyricsTrackTitle.textContent = track.title;
  lyricsContent.textContent = 'Loading...';
  lyricsContent.classList.remove('empty-state');
  lyricsSidebar.classList.add('open');

  try {
    const { lyrics } = await apiFetch(`/tracks/${track.id}/lyrics`);
    if (lyrics) {
      renderLyricsText(lyrics);
      lyricsContent.classList.remove('empty-state');
    } else {
      lrcLines = [];
      lyricsContent.textContent = 'No lyrics embedded in this file.';
      lyricsContent.classList.add('empty-state');
    }
  } catch (err) {
    lrcLines = [];
    lyricsContent.textContent = 'Failed to load lyrics.';
    lyricsContent.classList.add('empty-state');
  }
}

lyricsBtn.addEventListener('click', () => {
  lyricsSidebar.classList.contains('open') ? lyricsSidebar.classList.remove('open') : openLyrics();
});
lyricsCloseBtn.addEventListener('click', () => lyricsSidebar.classList.remove('open'));
let queue = [];
let queueIndex = -1;

const apiKeyModal = document.getElementById('api-key-modal');
const apiKeyForm = document.getElementById('api-key-form');
const apiKeyInput = document.getElementById('api-key-input');
const apiKeyError = document.getElementById('api-key-error');

let pendingKeyResolvers = [];

function promptForApiKey(errorMessage) {
  apiKeyError.textContent = errorMessage || '';
  apiKeyModal.classList.remove('hidden');
  apiKeyInput.value = '';
  apiKeyInput.focus();
  return new Promise((resolve) => pendingKeyResolvers.push(resolve));
}

apiKeyForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const value = apiKeyInput.value.trim();
  if (!value) return;
  apiKey = value;
  localStorage.setItem('apiKey', apiKey);
  apiKeyModal.classList.add('hidden');
  const resolvers = pendingKeyResolvers;
  pendingKeyResolvers = [];
  resolvers.forEach((resolve) => resolve());
});

async function ensureApiKey(errorMessage) {
  if (apiKey && !errorMessage) return;
  await promptForApiKey(errorMessage);
}

async function apiFetch(path, options = {}) {
  await ensureApiKey();
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { 'X-API-Key': apiKey, ...(options.headers || {}) },
  });
  if (res.status === 401) {
    localStorage.removeItem('apiKey');
    apiKey = null;
    await ensureApiKey('Invalid API key, try again.');
    return apiFetch(path, options);
  }
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

function jsonBody(obj) {
  return { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) };
}

function fetchPlaylists() {
  return apiFetch('/playlists');
}

function fetchPlaylist(id) {
  return apiFetch(`/playlists/${id}`);
}

function createPlaylistRequest(name) {
  return apiFetch('/playlists', { method: 'POST', ...jsonBody({ name }) });
}

function addTrackToPlaylistRequest(playlistId, trackId) {
  return apiFetch(`/playlists/${playlistId}/tracks`, { method: 'POST', ...jsonBody({ track_id: trackId }) });
}

function removeTrackFromPlaylistRequest(playlistId, trackId) {
  return apiFetch(`/playlists/${playlistId}/tracks/${trackId}`, { method: 'DELETE' });
}

function deletePlaylistRequest(playlistId) {
  return apiFetch(`/playlists/${playlistId}`, { method: 'DELETE' });
}

function formatDuration(sec) {
  if (sec == null) return '';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function formatRelativeTime(isoString) {
  // played_at is stored as SQLite's datetime('now') — UTC, no offset marker — append
  // 'Z' so the browser parses it as UTC instead of assuming local time.
  const then = new Date(isoString.replace(' ', 'T') + 'Z');
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

async function getCoverUrl(albumId) {
  if (coverCache.has(albumId)) return coverCache.get(albumId);
  try {
    const data = await apiFetch(`/cover/${albumId}`);
    coverCache.set(albumId, data.url);
    return data.url;
  } catch {
    coverCache.set(albumId, null);
    return null;
  }
}

function setBreadcrumbs(items) {
  breadcrumbs.innerHTML = '';
  items.forEach((item, i) => {
    if (i > 0) breadcrumbs.appendChild(document.createTextNode(' / '));
    if (item.onClick) {
      const a = document.createElement('a');
      a.textContent = item.label;
      a.onclick = item.onClick;
      breadcrumbs.appendChild(a);
    } else {
      breadcrumbs.appendChild(document.createTextNode(item.label));
    }
  });
}

async function showArtists() {
  setBreadcrumbs([{ label: 'Artists' }]);
  const artists = await apiFetch('/artists');
  content.innerHTML = '';
  if (artists.length === 0) {
    content.innerHTML = '<div class="empty">No artists yet — run scripts/ingest.py to add music.</div>';
    return;
  }
  const ul = document.createElement('ul');
  ul.className = 'artist-list';
  artists.forEach((a) => {
    const li = document.createElement('li');
    li.textContent = a.name;
    li.onclick = () => goToArtist(a.id, a.name);
    ul.appendChild(li);
  });
  content.appendChild(ul);
}

async function showArtistAlbums(artistId, artistName = null) {
  if (!artistName) {
    const artists = await apiFetch('/artists');
    const found = artists.find((a) => a.id === artistId);
    artistName = found ? found.name : 'Unknown Artist';
  }
  setBreadcrumbs([
    { label: 'Artists', onClick: goHome },
    { label: artistName },
  ]);
  const albums = await apiFetch(`/artists/${artistId}/albums`);
  content.innerHTML = '';
  content.appendChild(await renderAlbumGrid(albums));
}

async function renderAlbumGrid(albums) {
  const grid = document.createElement('div');
  grid.className = 'album-grid';
  for (const album of albums) {
    const card = document.createElement('div');
    card.className = 'album-card';
    card.onclick = () => goToAlbum(album.id);

    const coverUrl = album.has_cover ? await getCoverUrl(album.id) : null;
    const discWrap = document.createElement('div');
    discWrap.className = 'disc-wrap';
    const vinyl = document.createElement('div');
    vinyl.className = 'vinyl';
    discWrap.appendChild(vinyl);
    if (coverUrl) {
      const img = document.createElement('img');
      img.className = 'sleeve';
      img.src = coverUrl;
      discWrap.appendChild(img);
    } else {
      const ph = document.createElement('div');
      ph.className = 'sleeve cover-placeholder';
      ph.textContent = '♪';
      discWrap.appendChild(ph);
    }
    card.appendChild(discWrap);

    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = album.title;
    card.appendChild(title);

    const subtitle = document.createElement('div');
    subtitle.className = 'subtitle';
    subtitle.textContent = [album.artist_name, album.year].filter(Boolean).join(' · ');
    card.appendChild(subtitle);

    grid.appendChild(card);
  }
  return grid;
}

async function showAlbum(albumId) {
  const album = await apiFetch(`/albums/${albumId}`);
  setBreadcrumbs([
    { label: 'Artists', onClick: goHome },
    { label: album.artist_name, onClick: () => goToArtist(album.artist_id, album.artist_name) },
    { label: album.title },
  ]);
  content.innerHTML = '';

  const heading = document.createElement('h2');
  heading.textContent = album.year ? `${album.title} (${album.year})` : album.title;
  content.appendChild(heading);

  const list = document.createElement('div');
  album.tracks.forEach((track, i) => {
    list.appendChild(buildTrackRow(track, { onClick: () => playFromAlbum(album, i) }));
  });
  content.appendChild(list);
}

function playQueue(tracks, index) {
  queue = tracks;
  queueIndex = index;
  playCurrent();
}

function playFromAlbum(album, index) {
  const tracks = album.tracks.map((t) => ({
    ...t,
    artist_name: album.artist_name,
    album_title: album.title,
    album_id: album.id,
  }));
  playQueue(tracks, index);
}

// --- Shared track row rendering (album view, search results, playlist view) ---

function buildTrackRow(track, { showTrackNo = true, subtitle = null, playlistId = null, onClick } = {}) {
  const row = document.createElement('div');
  row.className = 'track-row';
  row.dataset.trackId = track.id;

  const noHtml = showTrackNo ? `<span class="track-no">${track.track_no ?? ''}</span>` : '';
  const titleHtml = subtitle
    ? `<span class="track-title">${track.title}<br><span style="color:var(--text-dim);font-size:0.8rem">${subtitle}</span></span>`
    : `<span class="track-title">${track.title}</span>`;

  row.innerHTML = `
    ${noHtml}
    ${titleHtml}
    <span class="track-duration">${formatDuration(track.duration_sec)}</span>
    <span class="track-actions"></span>
  `;

  const actions = row.querySelector('.track-actions');

  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'action-btn add-btn';
  addBtn.title = 'Add to playlist';
  addBtn.textContent = '+';
  addBtn.onclick = (e) => {
    e.stopPropagation();
    openAddToPlaylistMenu(track.id, addBtn);
  };
  actions.appendChild(addBtn);

  if (playlistId != null) {
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'action-btn remove-btn';
    removeBtn.title = 'Remove from playlist';
    removeBtn.textContent = '×';
    removeBtn.onclick = async (e) => {
      e.stopPropagation();
      await removeTrackFromPlaylistRequest(playlistId, track.id);
      showPlaylist(playlistId);
    };
    actions.appendChild(removeBtn);
  }

  if (onClick) row.addEventListener('click', onClick);
  return row;
}

// --- Recently played ---

async function showRecent() {
  setBreadcrumbs([{ label: 'Recently Played' }]);
  const tracks = await apiFetch('/recent');
  content.innerHTML = '';

  if (tracks.length === 0) {
    content.innerHTML = '<div class="empty">Nothing played yet.</div>';
    return;
  }

  const list = document.createElement('div');
  tracks.forEach((track, i) => {
    const row = buildTrackRow(track, {
      showTrackNo: false,
      subtitle: `${track.artist_name} — ${track.album_title} · ${formatRelativeTime(track.played_at)}`,
      onClick: () => playQueue(tracks, i),
    });
    list.appendChild(row);
  });
  content.appendChild(list);
}

// --- Playlists ---

async function showPlaylists() {
  setBreadcrumbs([{ label: 'Playlists' }]);
  const playlists = await fetchPlaylists();
  content.innerHTML = '';

  const newBtn = document.createElement('button');
  newBtn.type = 'button';
  newBtn.className = 'new-playlist-btn';
  newBtn.textContent = '+ New Playlist';
  newBtn.onclick = () => openCreatePlaylistModal();
  content.appendChild(newBtn);

  if (playlists.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No playlists yet.';
    content.appendChild(empty);
    return;
  }

  const ul = document.createElement('ul');
  ul.className = 'artist-list';
  playlists.forEach((p) => {
    const li = document.createElement('li');
    li.textContent = `${p.name} (${p.track_count})`;
    li.onclick = () => goToPlaylist(p.id);
    ul.appendChild(li);
  });
  content.appendChild(ul);
}

async function showPlaylist(playlistId) {
  const playlist = await fetchPlaylist(playlistId);
  setBreadcrumbs([
    { label: 'Playlists', onClick: goToPlaylists },
    { label: playlist.name },
  ]);
  content.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'playlist-header';

  const heading = document.createElement('h2');
  heading.textContent = playlist.name;
  header.appendChild(heading);

  const deleteBtn = document.createElement('button');
  deleteBtn.type = 'button';
  deleteBtn.className = 'action-btn remove-btn delete-playlist-btn';
  deleteBtn.textContent = 'Delete playlist';
  deleteBtn.onclick = async () => {
    await deletePlaylistRequest(playlistId);
    goToPlaylists();
  };
  header.appendChild(deleteBtn);
  content.appendChild(header);

  if (playlist.tracks.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No tracks yet — use the + button on any track to add it here.';
    content.appendChild(empty);
    return;
  }

  const list = document.createElement('div');
  playlist.tracks.forEach((track, i) => {
    const row = buildTrackRow(track, {
      showTrackNo: false,
      subtitle: `${track.artist_name} — ${track.album_title}`,
      playlistId,
      onClick: () => playQueue(playlist.tracks, i),
    });
    list.appendChild(row);
  });
  content.appendChild(list);
}

// --- Add-to-playlist dropdown ---

let activeDropdown = null;

function closeDropdown() {
  if (activeDropdown) {
    activeDropdown.remove();
    activeDropdown = null;
    document.removeEventListener('click', closeDropdownOnOutsideClick);
  }
}

function closeDropdownOnOutsideClick(e) {
  if (activeDropdown && !activeDropdown.contains(e.target)) closeDropdown();
}

async function openAddToPlaylistMenu(trackId, anchorEl) {
  closeDropdown();
  const playlists = await fetchPlaylists();

  const menu = document.createElement('div');
  menu.className = 'playlist-dropdown';

  if (playlists.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'dropdown-empty';
    empty.textContent = 'No playlists yet';
    menu.appendChild(empty);
  } else {
    playlists.forEach((p) => {
      const item = document.createElement('div');
      item.className = 'dropdown-item';
      item.textContent = p.name;
      item.onclick = async () => {
        await addTrackToPlaylistRequest(p.id, trackId);
        closeDropdown();
      };
      menu.appendChild(item);
    });
  }

  const divider = document.createElement('div');
  divider.className = 'dropdown-divider';
  menu.appendChild(divider);

  const newItem = document.createElement('div');
  newItem.className = 'dropdown-item';
  newItem.textContent = '+ New playlist...';
  newItem.onclick = () => {
    closeDropdown();
    openCreatePlaylistModal(trackId);
  };
  menu.appendChild(newItem);

  document.body.appendChild(menu);
  const rect = anchorEl.getBoundingClientRect();
  menu.style.top = `${rect.bottom + 4}px`;
  menu.style.left = `${Math.min(rect.left, window.innerWidth - 200)}px`;

  activeDropdown = menu;
  setTimeout(() => document.addEventListener('click', closeDropdownOnOutsideClick), 0);
}

// --- Create-playlist modal ---

const playlistModal = document.getElementById('playlist-modal');
const playlistForm = document.getElementById('playlist-form');
const playlistNameInput = document.getElementById('playlist-name-input');
const playlistError = document.getElementById('playlist-error');

let pendingTrackIdForNewPlaylist = null;

function openCreatePlaylistModal(trackIdToAddAfterCreate = null) {
  pendingTrackIdForNewPlaylist = trackIdToAddAfterCreate;
  playlistError.textContent = '';
  playlistNameInput.value = '';
  playlistModal.classList.remove('hidden');
  playlistNameInput.focus();
}

playlistForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = playlistNameInput.value.trim();
  if (!name) return;
  try {
    const playlist = await createPlaylistRequest(name);
    playlistModal.classList.add('hidden');
    if (pendingTrackIdForNewPlaylist != null) {
      await addTrackToPlaylistRequest(playlist.id, pendingTrackIdForNewPlaylist);
    }
    goToPlaylist(playlist.id);
  } catch (err) {
    playlistError.textContent = String(err.message).includes('409')
      ? 'A playlist with that name already exists.'
      : 'Failed to create playlist.';
  }
});

playlistsBtn.addEventListener('click', () => goToPlaylists());
recentBtn.addEventListener('click', () => goToRecent());

async function playCurrent() {
  const track = queue[queueIndex];
  if (!track) return;
  const { url } = await apiFetch(`/stream/${track.id}`);
  audio.src = url;
  audio.loop = loopMode === 'one';
  audio.play();

  nowTitle.textContent = track.title;
  nowArtist.textContent = `${track.artist_name} — ${track.album_title}`;
  nowCover.src = (await getCoverUrl(track.album_id)) || '';

  if (lyricsSidebar.classList.contains('open')) openLyrics();

  document.querySelectorAll('.track-row').forEach((row) => {
    row.classList.toggle('playing', Number(row.dataset.trackId) === track.id);
  });

  startStatsLoop(track);
}

// --- Live bitrate / streaming metrics ---

let statsInterval = null;
const STATS_WINDOW_MS = 10000; // smooth throughput over a rolling window, not one snapshot

function stopStatsLoop() {
  if (statsInterval) clearInterval(statsInterval);
  statsInterval = null;
  nowStats.innerHTML = '';
}

function startStatsLoop(track) {
  stopStatsLoop();
  const bitrateBps = track.size_bytes && track.duration_sec
    ? (track.size_bytes * 8) / track.duration_sec
    : null;

  const meta = { bitrateBps, sampleRate: track.sample_rate, bitDepth: track.bit_depth, durationSec: track.duration_sec };
  renderStats({ ...meta, throughputBps: null, bufferedAhead: 0, fullyBuffered: false });

  // history of {time, bufferedEnd} samples, trimmed to the last STATS_WINDOW_MS —
  // browsers fetch media in discrete chunks, not a smooth stream, so a single
  // instantaneous 1s delta can land in a between-chunks lull and misreport a
  // stall that never actually happens. Averaging over several seconds smooths
  // that jitter out while still catching a genuine sustained shortfall.
  const history = [{ time: performance.now(), bufferedEnd: 0 }];

  statsInterval = setInterval(() => {
    const bufferedEnd = audio.buffered.length ? audio.buffered.end(audio.buffered.length - 1) : 0;
    const now = performance.now();

    history.push({ time: now, bufferedEnd });
    while (history.length > 1 && now - history[0].time > STATS_WINDOW_MS) {
      history.shift();
    }

    let throughputBps = null;
    const windowStart = history[0];
    const windowSeconds = (now - windowStart.time) / 1000;
    if (bitrateBps && windowSeconds > 0.5) {
      const deltaSeconds = Math.max(0, bufferedEnd - windowStart.bufferedEnd);
      const deltaBytes = deltaSeconds * (bitrateBps / 8);
      throughputBps = (deltaBytes / windowSeconds) * 8;
    }

    const fullyBuffered = Boolean(meta.durationSec && bufferedEnd >= meta.durationSec - 0.5);
    renderStats({
      ...meta,
      throughputBps,
      bufferedAhead: Math.max(0, bufferedEnd - audio.currentTime),
      fullyBuffered,
    });
  }, 1000);
}

const SAFE_BUFFER_SECONDS = 10; // enough runway that a momentary fetch pause isn't a real risk

function renderStats({ bitrateBps, sampleRate, bitDepth, throughputBps, bufferedAhead, fullyBuffered }) {
  const format = [sampleRate ? `${(sampleRate / 1000).toFixed(1)}kHz` : null, bitDepth ? `${bitDepth}-bit` : null]
    .filter(Boolean)
    .join('/');
  const bitrateKbps = bitrateBps ? Math.round(bitrateBps / 1000) : null;
  const hasSafeMargin = bufferedAhead >= SAFE_BUFFER_SECONDS;

  let barPct = 0;
  let barClass = 'stat-bar-red';
  let statusText = 'buffering…';

  if (fullyBuffered) {
    barPct = 100;
    barClass = 'stat-bar-green';
    statusText = 'fully buffered';
  } else if (throughputBps != null && bitrateBps) {
    const ratio = throughputBps / bitrateBps;
    const kBps = Math.round(throughputBps / 8 / 1024);
    statusText = `${kBps} KB/s (${ratio.toFixed(1)}x realtime)`;

    if (hasSafeMargin) {
      // Enough buffer already sitting in reserve that a momentary fetch pause
      // (browsers throttle progressive-download fetching once comfortably
      // ahead) isn't a real risk, even though the instantaneous rate reads low.
      barPct = 100;
      barClass = 'stat-bar-green';
    } else {
      barPct = Math.min(100, (ratio / 2) * 100);
      barClass = ratio >= 1.5 ? 'stat-bar-green' : ratio >= 1 ? 'stat-bar-yellow' : 'stat-bar-red';
    }
  } else if (hasSafeMargin) {
    barPct = 100;
    barClass = 'stat-bar-green';
  }

  nowStats.innerHTML = `
    <span>FLAC ${format}</span>
    <span>${bitrateKbps ? bitrateKbps + ' kbps avg' : ''}</span>
    <span>${statusText}</span>
    <span class="stat-bar-track"><span class="stat-bar-fill ${barClass}" style="width:${barPct}%"></span></span>
    <span>${bufferedAhead.toFixed(1)}s buffered ahead</span>
  `;
}

audio.addEventListener('ended', () => {
  // loopMode === 'one' never reaches here — native audio.loop restarts the
  // track itself without firing 'ended'.
  if (queueIndex + 1 < queue.length) {
    queueIndex += 1;
    playCurrent();
  } else if (loopMode === 'all' && queue.length > 0) {
    queueIndex = 0;
    playCurrent();
  }
});

async function runSearch(query) {
  setBreadcrumbs([{ label: `Search: "${query}"` }]);
  const results = await apiFetch(`/search?q=${encodeURIComponent(query)}`);
  content.innerHTML = '';

  if (results.artists.length) {
    const h = document.createElement('h3');
    h.textContent = 'Artists';
    content.appendChild(h);
    const ul = document.createElement('ul');
    ul.className = 'artist-list';
    results.artists.forEach((a) => {
      const li = document.createElement('li');
      li.textContent = a.name;
      li.onclick = () => goToArtist(a.id, a.name);
      ul.appendChild(li);
    });
    content.appendChild(ul);
  }

  if (results.albums.length) {
    const h = document.createElement('h3');
    h.textContent = 'Albums';
    content.appendChild(h);
    content.appendChild(await renderAlbumGrid(results.albums));
  }

  if (results.tracks.length) {
    const h = document.createElement('h3');
    h.textContent = 'Tracks';
    content.appendChild(h);
    const list = document.createElement('div');
    results.tracks.forEach((track) => {
      const row = buildTrackRow(track, {
        showTrackNo: false,
        onClick: async () => {
          const album = await apiFetch(`/albums/${track.album_id}`);
          const index = album.tracks.findIndex((t) => t.id === track.id);
          playFromAlbum(album, index);
        },
      });
      list.appendChild(row);
    });
    content.appendChild(list);
  }

  if (!results.artists.length && !results.albums.length && !results.tracks.length) {
    content.innerHTML = '<div class="empty">No results.</div>';
  }
}

function showUploadStatus(text, isError) {
  uploadStatus.textContent = text;
  uploadStatus.classList.remove('hidden');
  uploadStatus.classList.toggle('error', Boolean(isError));
}

async function uploadFiles(files) {
  await ensureApiKey();

  uploadBtn.disabled = true;
  showUploadStatus(`Uploading ${files.length} file(s)...`);

  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'X-API-Key': apiKey },
      body: formData,
    });

    if (res.status === 401) {
      localStorage.removeItem('apiKey');
      apiKey = null;
      await ensureApiKey('Invalid API key, try again.');
      uploadBtn.disabled = false;
      return uploadFiles(files);
    }

    if (!res.ok) throw new Error(`upload failed: ${res.status}`);
    const data = await res.json();

    const parts = [];
    if (data.uploaded.length) parts.push(`${data.uploaded.length} added`);
    if (data.skipped.length) parts.push(`${data.skipped.length} already in library`);
    if (data.failed.length) parts.push(`${data.failed.length} failed`);
    showUploadStatus(parts.join(', ') || 'Nothing to upload', data.failed.length > 0);

    if (data.failed.length) {
      console.warn('Upload failures:', data.failed);
    }
    if (data.uploaded.length) {
      coverCache.clear();
      goHome();
    }
  } catch (err) {
    showUploadStatus(`Upload failed: ${err.message}`, true);
  } finally {
    uploadBtn.disabled = false;
    setTimeout(() => uploadStatus.classList.add('hidden'), 8000);
  }
}

uploadBtn.addEventListener('click', () => uploadInput.click());
uploadInput.addEventListener('change', () => {
  const files = Array.from(uploadInput.files);
  uploadInput.value = '';
  if (files.length) uploadFiles(files);
});

let searchTimeout;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  const q = searchInput.value.trim();
  searchTimeout = setTimeout(() => {
    if (q) goToSearch(q);
    else goHome();
  }, 300);
});

// --- Client-side routing (History API) ---
//
// Every view has a real URL: '/', '/artists/:id', '/albums/:id', '/playlists',
// '/playlists/:id', '/search?q=...'. The goTo* helpers push a history entry and
// render immediately using data already on hand (e.g. an artist's name from the
// list row that was clicked). route() re-derives the view purely from
// location.pathname/search — used on initial load and on back/forward
// (popstate), where no in-memory context is available. The backend serves the
// same index.html for any of these paths (see the SPA catch-all in app/main.py),
// so a bookmark or refresh at e.g. /playlists/3 lands here and route() renders it.

function goHome() {
  history.pushState({}, '', '/');
  showArtists();
}

function goToArtist(id, name = null) {
  history.pushState({}, '', `/artists/${id}`);
  showArtistAlbums(id, name);
}

function goToAlbum(id) {
  history.pushState({}, '', `/albums/${id}`);
  showAlbum(id);
}

function goToRecent() {
  history.pushState({}, '', '/recent');
  showRecent();
}

function goToPlaylists() {
  history.pushState({}, '', '/playlists');
  showPlaylists();
}

function goToPlaylist(id) {
  history.pushState({}, '', `/playlists/${id}`);
  showPlaylist(id);
}

function goToSearch(query) {
  history.pushState({}, '', `/search?q=${encodeURIComponent(query)}`);
  runSearch(query);
}

function route() {
  const path = location.pathname;
  const params = new URLSearchParams(location.search);
  let m;

  if (path === '/') return showArtists();
  if ((m = path.match(/^\/artists\/(\d+)\/?$/))) return showArtistAlbums(Number(m[1]));
  if ((m = path.match(/^\/albums\/(\d+)\/?$/))) return showAlbum(Number(m[1]));
  if (path === '/recent' || path === '/recent/') return showRecent();
  if (path === '/playlists' || path === '/playlists/') return showPlaylists();
  if ((m = path.match(/^\/playlists\/(\d+)\/?$/))) return showPlaylist(Number(m[1]));
  if (path === '/search' || path === '/search/') {
    const q = params.get('q') || '';
    searchInput.value = q;
    return runSearch(q);
  }

  history.replaceState({}, '', '/');
  return showArtists();
}

window.addEventListener('popstate', route);
document.querySelector('header h1').addEventListener('click', goHome);

route();
