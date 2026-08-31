CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(id),
    title TEXT NOT NULL,
    year INTEGER,
    cover_art_key TEXT,
    UNIQUE (artist_id, title)
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER NOT NULL REFERENCES albums(id),
    title TEXT NOT NULL,
    track_no INTEGER,
    duration_sec REAL,
    r2_key TEXT NOT NULL UNIQUE,
    file_hash TEXT NOT NULL UNIQUE,
    bit_depth INTEGER,
    sample_rate INTEGER,
    size_bytes INTEGER,
    lyrics TEXT
);

CREATE INDEX IF NOT EXISTS idx_tracks_album_id ON tracks (album_id);
CREATE INDEX IF NOT EXISTS idx_albums_artist_id ON albums (artist_id);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist_id ON playlist_tracks (playlist_id);

CREATE TABLE IF NOT EXISTS track_artists (
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (track_id, artist_id)
);

CREATE INDEX IF NOT EXISTS idx_track_artists_track_id ON track_artists (track_id);
CREATE INDEX IF NOT EXISTS idx_track_artists_artist_id ON track_artists (artist_id);

CREATE TABLE IF NOT EXISTS play_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    played_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_play_history_track_id ON play_history (track_id);
CREATE INDEX IF NOT EXISTS idx_play_history_played_at ON play_history (played_at);
