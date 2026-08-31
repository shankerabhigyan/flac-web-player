# Abhigyan's FLAC Player

Personal pipeline + API for storing a FLAC library in Cloudflare R2 and streaming it to
any device, with near-zero ongoing cost (R2 has $0 egress).

## Stack

- **Storage:** Cloudflare R2 (S3-compatible, $0 egress)
- **Metadata DB:** SQLite
- **Backend:** FastAPI + boto3
- **Tags:** mutagen
- **Clients:** Subsonic API compatibility (Symfonium, Substreamer, DSub, ...)

## Status

- [x] Phase 0 — project skeleton, deps
- [x] Phase 0 — R2 bucket + credentials configured
- [x] Phase 1 — ingestion pipeline
- [x] Phase 2 — core backend API
- [x] Phase 3 — Subsonic compatibility
- [x] Phase 5 — web player (moved up: wanted for local PC use before deployment)
- [ ] Phase 4 — deployment
- [ ] Phase 6 — on-demand transcoding (optional)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in R2 credentials
python scripts/check_r2.py  # verify R2 connectivity
python -m scripts.ingest /path/to/flac/library  # Phase 1: ingest a local library
python -m app.main  # run the API — always port 8123, with reload; don't use bare `uvicorn app.main:app`, it defaults to port 8000
```

## API (Phase 2)

All JSON API routes live under **`/api`** (all except `/health` require an `X-API-Key` header
matching `API_AUTH_KEY` in `.env`). This is a distinct namespace from the web player's own page
routes (`/`, `/playlists`, `/albums/5`, etc. — see "Client-side routing" below) so the two never
collide: loading `/playlists` in a browser renders the app, while `/api/playlists` returns JSON.

- `GET /api/artists`
- `GET /api/artists/{artist_id}/albums`
- `GET /api/albums/{album_id}` — includes track list
- `GET /api/tracks/{track_id}`
- `GET /api/recent?limit=50` — most recently played tracks, one row per track (deduped to the
  latest play so a looped song doesn't flood the list)
- `GET /api/search?q=...` — matches across artists/albums/tracks
- `GET /api/stream/{track_id}` — returns a presigned R2 URL (1hr TTL), the client streams directly from R2
- `GET /api/cover/{album_id}` — same presigned-URL pattern for artwork
- `POST /api/upload` — multipart file upload (`files`, one or more `.flac`), runs each through the
  same tag-extract → R2 upload → catalog upsert pipeline as `scripts/ingest.py` (shared logic
  in `app/ingest.py`). Returns `{uploaded, skipped, failed}`. Also wired into the web player as
  an "Upload" button in the header.
- `GET/POST /api/playlists`, `GET/DELETE /api/playlists/{id}`, `POST /api/playlists/{id}/tracks`,
  `DELETE /api/playlists/{id}/tracks/{track_id}`, `PUT /api/playlists/{id}/order` — user-curated
  collections of tracks, independent of artist/album. Adding is idempotent (re-adding a track
  already in a playlist is a no-op); tracks are cascade-deleted from playlists if the underlying
  track row is ever removed.
- `GET /health` — unauthenticated, not under `/api` (kept simple for uptime checks).

## Subsonic API (Phase 3)

Endpoints under `/rest/*` (both with and without the traditional `.view` suffix), for use with
any Subsonic-compatible client (Symfonium, Substreamer, DSub, play:Sub, Amperfy, ...):

- Server URL: `http://<host>:8123` (adjust port/host for wherever you deploy)
- Username: `SUBSONIC_USERNAME` in `.env`
- Password: `SUBSONIC_PASSWORD` in `.env`

Implemented: `ping`, `getLicense`, `getArtists`, `getArtist`, `getAlbumList2`, `getAlbum`,
`search3`, `stream`, `getCoverArt`. `stream`/`getCoverArt` return an HTTP 302 redirect to a
presigned R2 URL rather than proxying bytes — consistent with the rest of the API.

**Scoping notes:**
- JSON-only (`f=json`) — XML responses aren't implemented. All the actively-relevant clients
  (Symfonium, Substreamer, current DSub builds) support requesting JSON.
- Uses the modern ID3-tag-based browsing endpoints (`getArtists`/`getArtist`/`getAlbum`), not
  the legacy folder-based `getIndexes`/`getMusicDirectory` — our catalog is natively
  artist/album/track relational, not filesystem-folder based, so ID3 mode is the natural fit
  and is what modern clients default to anyway.
- `getAlbumList2` was added beyond the original plan's endpoint list because most clients need
  it to populate their default "Albums" browse tab.

## Web player (Phase 5)

Served directly by the FastAPI app at `/` (same origin as the REST API, so no CORS setup
needed). Plain HTML/CSS/vanilla JS — no build step, no Node dependency. On first load it
prompts for the `API_AUTH_KEY` (stored in the browser's `localStorage` after that). Features:
artist list → album grid → track list → play, a persistent bottom player bar with native
`<audio>` controls, auto-advance to the next track in the album on end, a debounced search
box covering artists/albums/tracks, a repeat toggle in the player bar (icon button, cycles Off → All → One — "One" delegates to the
native `<audio loop>` so a single track repeats without any JS involvement, and shows a small
"1" badge; "All" wraps the queue back to index 0 once the last track ends, both indicated via
an accent-colored active state on the icon), live streaming
metrics (see below), playlists: a
"Playlists" button in the header, a "+" button on every track row (album view, search results,
and playlist view) opening a dropdown to add that track to an existing playlist or create a new
one on the spot, and a "×" button to remove a track when viewing a playlist; and a "Recent"
button showing your most recently played tracks (see below).

### Recently played

Every time a track is streamed — through the web player *or* a Subsonic client (Symfonium,
Substreamer, etc.) — `app/routers/stream.py` and `app/routers/subsonic.py` both log it to a
`play_history` table via `app/db.py`'s `record_play()`, right at the point they hand out the
presigned stream URL. This means play history is tracked server-side for every playback source,
not just the web UI. The "Recent" view (`GET /api/recent`) shows one row per track (deduped to
its latest play, so repeatedly looping one song doesn't flood the list with the same entry) with
a relative-time label ("just now", "5m ago", "3h ago", "2d ago"), most recent first.

### Lyrics

A lyrics icon button in the player bar slides in a sidebar showing whatever is embedded in the
current track's own `lyrics` Vorbis comment tag (`app/tags.py` reads it the same way as any
other tag; `GET /api/tracks/{id}/lyrics` serves it on demand, kept out of the main track list
responses since it can be long text not needed for browsing). Shows "No lyrics embedded in this
file" when the tag is absent. **This only ever surfaces text already embedded in your own files
— it does not fetch lyrics from any external source.** Not every track has this tag populated;
it depends entirely on whatever ripped/tagged the file.

If the embedded text is in **LRC format** (`[mm:ss.xx] line`, the standard synced-lyrics
convention), `app.js`'s `parseLrc` extracts the per-line timestamps and the sidebar highlights
the current line + auto-scrolls it into view as the track plays, tracking `audio.currentTime`
via the `timeupdate` event. Plain unsynced text (no timestamps) falls back to a static block,
same as before. The sidebar stays open across a track change and refreshes to the new track's
lyrics automatically.

### Client-side routing

Every view has a real, bookmarkable URL, kept in sync with the browser's History API:

- `/` — Artists list (also reachable by clicking the header title)
- `/artists/:id` — an artist's albums
- `/albums/:id` — album detail / track list
- `/search?q=...` — search results
- `/recent` — recently played tracks
- `/playlists` — playlists list
- `/playlists/:id` — playlist detail

Back/forward work correctly between views, and loading any of these URLs directly (a bookmark,
a refresh, a shared link) renders the right view on first load — the backend's SPA catch-all
(`app/main.py`, registered after every other route) serves `index.html` for any path not matched
by `/api/*`, `/static/*`, `/health`, or `/rest/*`, and `app.js`'s `route()` reads
`location.pathname`/`search` to render accordingly. Internal navigation goes through `goTo*`
helpers (`goHome`, `goToArtist`, `goToAlbum`, `goToPlaylists`, `goToPlaylist`, `goToSearch`) that
push a history entry and render immediately using data already on hand (e.g. an artist's name
from the row just clicked); `route()` itself re-derives everything from the URL alone, since
that's all that's available on a fresh load or a back/forward navigation.

### Live bitrate / streaming metrics

Under the player bar: format (`44.1kHz/16-bit`), average bitrate (derived from `size_bytes` /
`duration_sec`), a live download-throughput readout with a color-coded health bar, and
"buffered ahead" (seconds of audio already downloaded past the current playback position).

Throughput is estimated client-side by sampling `audio.buffered` over a rolling **10-second**
window (not a single 1-second snapshot) — browsers fetch progressive media in discrete chunks,
so a single-instant sample can land in a between-chunks lull and misreport a stall that never
happens; averaging over 10s smooths that out while still catching a genuine sustained shortfall
(verified against simulated bursty-fetch patterns before picking the window size). The bar is
also forced green whenever "buffered ahead" is ≥10s, regardless of the instantaneous rate —
a comfortable safety cushion means a momentary fetch pause isn't a real risk even if throughput
reads low or zero at that instant. Below that margin, it's ratio-based: green at ≥1.5x realtime,
yellow at 1-1.5x, red below 1x. Shows "fully buffered" once the whole track has downloaded.

## Testing & CI

```bash
pip install -r requirements-dev.txt
ruff check .   # lint
pytest -v      # unit + API tests
```

Tests never touch real R2 or a real `.env` — `tests/conftest.py` sets dummy credentials via
env vars (which take priority over `.env`) before the app is imported, and every test runs
against an isolated temp SQLite file (`app.db.DB_PATH` is monkeypatched per test). R2 calls are
never made for real: `presigned_get_url` is monkeypatched at the router level for stream/cover
tests, and `app/storage.py` itself is tested against a fake boto3-shaped client. Coverage
focuses on the parts that have actually broken before or are easy to regress silently: the
multi-artist `track_artists` linking, recent-plays dedup/ordering, playlist CRUD + cascade
delete, FLAC tag parsing (`_parse_artist_names` et al.), and Subsonic token/password auth.

GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on every push and PR to
`master`/`main`.

## Favicon

`app/static/favicon.webp` — a vinyl record icon, swapped in to replace the original inline
gradient-SVG placeholder. Referenced via `<link rel="icon" type="image/webp" href="/static/favicon.webp">`.

## Theme

Neon Synthwave: near-black background (`#0d0b1a`/`#17142b`), magenta/cyan gradient accents
(`--accent`/`--accent2` in `style.css`) on the header/player-bar borders, the playing-track
highlight, the upload button's hover glow, and the modal's submit button. Chosen from three
mocked-up directions (Vinyl Amber, Neon Synthwave, Aurora Teal-Violet) previewed live in-browser
before committing.

## Data model

SQLite catalog at `data/catalog.db` (gitignored): `artists` / `albums` / `tracks` /
`track_artists` / `playlists` / `playlist_tracks`, see `app/schema.sql`. R2 object keys follow
`artist/album/NN - title.flac` (using the track's primary/first-credited artist), cover art at
`artist/album/cover.{jpg,png}`. Ingestion is idempotent — re-running dedupes by file content
hash (sha256), so renamed/moved local files aren't re-uploaded.

### Multi-artist tracks

A track's `artist` tag can credit more than one person (e.g. `"Asfar Hussain; Xulfi"`, or the
singer/composer/lyricist convention common in film-soundtrack tagging). `app/tags.py` splits
these on `;` into an ordered list (`TrackTags.artists`, first = primary), and `app/ingest.py`
links the track to *every* credited artist via the `track_artists` join table
(`app/db.py`'s `link_track_artists`), not just the primary one. `albums.artist_id` still holds
one "display" artist per album (the primary artist of the first-ingested track — used for the
album's subtitle/cover-art grouping), but an artist's **own** page
(`GET /api/artists/{id}/albums`, and the Subsonic `getArtist`) is resolved via `track_artists`
membership (`app/db.py`'s `get_artist_albums`), so it shows every album containing *any* track
credited to them — solo work and featured/collab tracks alike, even when a collab album's own
display artist is someone else. This means "Asfar Hussain" and "Xulfi" each show up once, with
their shared collab album appearing under both — rather than a compound string like
`"Asfar Hussain; Xulfi"` fragmenting into its own disconnected artist entry.
