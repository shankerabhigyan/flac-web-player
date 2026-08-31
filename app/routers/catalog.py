import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.db import get_artist_albums, get_connection, get_recent_tracks, get_track_lyrics
from app.schemas import (
    AlbumDetailOut,
    AlbumOut,
    ArtistOut,
    RecentTrackOut,
    SearchOut,
    TrackLyricsOut,
    TrackOut,
)

router = APIRouter(dependencies=[Depends(require_api_key)])

_ALBUM_SELECT = """
    SELECT albums.id, albums.title, albums.year, albums.artist_id, albums.cover_art_key,
           artists.name AS artist_name
    FROM albums JOIN artists ON artists.id = albums.artist_id
"""


def _album_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "year": row["year"],
        "artist_id": row["artist_id"],
        "artist_name": row["artist_name"],
        "has_cover": row["cover_art_key"] is not None,
    }


def _track_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "track_no": row["track_no"],
        "duration_sec": row["duration_sec"],
        "album_id": row["album_id"],
        "bit_depth": row["bit_depth"],
        "sample_rate": row["sample_rate"],
        "size_bytes": row["size_bytes"],
    }


@router.get("/artists", response_model=list[ArtistOut])
def list_artists():
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM artists ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@router.get("/artists/{artist_id}/albums", response_model=list[AlbumOut])
def list_artist_albums(artist_id: int):
    with get_connection() as conn:
        artist = conn.execute("SELECT id FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(404, "Artist not found")
        rows = get_artist_albums(conn, artist_id)
    return [_album_out(r) for r in rows]


@router.get("/albums/{album_id}", response_model=AlbumDetailOut)
def get_album(album_id: int):
    with get_connection() as conn:
        row = conn.execute(f"{_ALBUM_SELECT} WHERE albums.id = ?", (album_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Album not found")
        track_rows = conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? ORDER BY track_no", (album_id,)
        ).fetchall()
    album = _album_out(row)
    album["tracks"] = [_track_out(t) for t in track_rows]
    return album


@router.get("/tracks/{track_id}", response_model=TrackOut)
def get_track(track_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Track not found")
    return _track_out(row)


@router.get("/tracks/{track_id}/lyrics", response_model=TrackLyricsOut)
def get_lyrics(track_id: int):
    with get_connection() as conn:
        track = conn.execute("SELECT 1 FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not track:
            raise HTTPException(404, "Track not found")
        lyrics = get_track_lyrics(conn, track_id)
    return {"lyrics": lyrics}


@router.get("/recent", response_model=list[RecentTrackOut])
def list_recent(limit: int = 50):
    with get_connection() as conn:
        rows = get_recent_tracks(conn, limit)
    return [
        {**_track_out(r), "artist_name": r["artist_name"], "album_title": r["album_title"], "played_at": r["played_at"]}
        for r in rows
    ]


@router.get("/search", response_model=SearchOut)
def search(q: str):
    like = f"%{q}%"
    with get_connection() as conn:
        artist_rows = conn.execute(
            "SELECT id, name FROM artists WHERE name LIKE ? ORDER BY name LIMIT 25", (like,)
        ).fetchall()
        album_rows = conn.execute(
            f"{_ALBUM_SELECT} WHERE albums.title LIKE ? ORDER BY albums.title LIMIT 25",
            (like,),
        ).fetchall()
        track_rows = conn.execute(
            "SELECT * FROM tracks WHERE title LIKE ? ORDER BY title LIMIT 25", (like,)
        ).fetchall()
    return {
        "artists": [dict(r) for r in artist_rows],
        "albums": [_album_out(r) for r in album_rows],
        "tracks": [_track_out(r) for r in track_rows],
    }
