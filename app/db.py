import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        _ensure_column(conn, "tracks", "size_bytes", "INTEGER")
        _ensure_column(conn, "tracks", "lyrics", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_or_create_artist(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM artists WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO artists (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_album(
    conn: sqlite3.Connection, artist_id: int, title: str, year: int | None
) -> tuple[int, str | None]:
    row = conn.execute(
        "SELECT id, cover_art_key FROM albums WHERE artist_id = ? AND title = ?",
        (artist_id, title),
    ).fetchone()
    if row:
        return row["id"], row["cover_art_key"]
    cur = conn.execute(
        "INSERT INTO albums (artist_id, title, year) VALUES (?, ?, ?)",
        (artist_id, title, year),
    )
    return cur.lastrowid, None


def set_album_cover(conn: sqlite3.Connection, album_id: int, cover_art_key: str) -> None:
    conn.execute(
        "UPDATE albums SET cover_art_key = ? WHERE id = ?", (cover_art_key, album_id)
    )


def track_exists_by_hash(conn: sqlite3.Connection, file_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tracks WHERE file_hash = ?", (file_hash,)
    ).fetchone()
    return row is not None


def insert_track(
    conn: sqlite3.Connection,
    album_id: int,
    title: str,
    track_no: int | None,
    duration_sec: float | None,
    r2_key: str,
    file_hash: str,
    bit_depth: int | None,
    sample_rate: int | None,
    size_bytes: int | None,
    lyrics: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO tracks
            (album_id, title, track_no, duration_sec, r2_key, file_hash, bit_depth, sample_rate, size_bytes, lyrics)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (album_id, title, track_no, duration_sec, r2_key, file_hash, bit_depth, sample_rate, size_bytes, lyrics),
    )
    return cur.lastrowid


def get_track_lyrics(conn: sqlite3.Connection, track_id: int) -> str | None:
    row = conn.execute("SELECT lyrics FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return row["lyrics"] if row else None


def record_play(conn: sqlite3.Connection, track_id: int) -> None:
    conn.execute("INSERT INTO play_history (track_id) VALUES (?)", (track_id,))


def get_recent_tracks(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    """Most recently played tracks, one row per track (deduped by latest play) so a
    looped/repeated track doesn't flood the list with consecutive duplicates."""
    return conn.execute(
        """
        SELECT tracks.*, albums.title AS album_title, albums.artist_id AS artist_id,
               artists.name AS artist_name, MAX(play_history.played_at) AS played_at
        FROM play_history
        JOIN tracks ON tracks.id = play_history.track_id
        JOIN albums ON albums.id = tracks.album_id
        JOIN artists ON artists.id = albums.artist_id
        GROUP BY tracks.id
        ORDER BY played_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def link_track_artists(conn: sqlite3.Connection, track_id: int, artist_names: list[str]) -> None:
    """Credit a track to one or more artists, preserving order (index 0 = primary)."""
    for position, name in enumerate(artist_names):
        artist_id = get_or_create_artist(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO track_artists (track_id, artist_id, position) VALUES (?, ?, ?)",
            (track_id, artist_id, position),
        )


def get_artist_albums(conn: sqlite3.Connection, artist_id: int) -> list[sqlite3.Row]:
    """Albums containing at least one track credited to this artist, at any position
    (primary or featured) — not just albums where they're the album's own display artist."""
    return conn.execute(
        """
        SELECT DISTINCT albums.id, albums.title, albums.year, albums.artist_id, albums.cover_art_key,
               artists.name AS artist_name
        FROM track_artists
        JOIN tracks ON tracks.id = track_artists.track_id
        JOIN albums ON albums.id = tracks.album_id
        JOIN artists ON artists.id = albums.artist_id
        WHERE track_artists.artist_id = ?
        ORDER BY albums.year, albums.title
        """,
        (artist_id,),
    ).fetchall()


def create_playlist(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
    return cur.lastrowid


def list_playlists(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT playlists.id, playlists.name, COUNT(playlist_tracks.track_id) AS track_count
        FROM playlists
        LEFT JOIN playlist_tracks ON playlist_tracks.playlist_id = playlists.id
        GROUP BY playlists.id
        ORDER BY playlists.name COLLATE NOCASE
        """
    ).fetchall()


def get_playlist(conn: sqlite3.Connection, playlist_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()


def delete_playlist(conn: sqlite3.Connection, playlist_id: int) -> None:
    conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))


def get_playlist_tracks(conn: sqlite3.Connection, playlist_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT tracks.*, albums.title AS album_title, albums.artist_id AS artist_id,
               artists.name AS artist_name
        FROM playlist_tracks
        JOIN tracks ON tracks.id = playlist_tracks.track_id
        JOIN albums ON albums.id = tracks.album_id
        JOIN artists ON artists.id = albums.artist_id
        WHERE playlist_tracks.playlist_id = ?
        ORDER BY playlist_tracks.position
        """,
        (playlist_id,),
    ).fetchall()


def add_track_to_playlist(conn: sqlite3.Connection, playlist_id: int, track_id: int) -> None:
    existing = conn.execute(
        "SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, track_id),
    ).fetchone()
    if existing:
        return
    next_position = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
        (playlist_id, track_id, next_position),
    )


def remove_track_from_playlist(conn: sqlite3.Connection, playlist_id: int, track_id: int) -> None:
    conn.execute(
        "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, track_id),
    )


def reorder_playlist_tracks(conn: sqlite3.Connection, playlist_id: int, track_ids: list[int]) -> None:
    for position, track_id in enumerate(track_ids):
        conn.execute(
            "UPDATE playlist_tracks SET position = ? WHERE playlist_id = ? AND track_id = ?",
            (position, playlist_id, track_id),
        )
