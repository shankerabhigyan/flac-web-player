import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.db import (
    add_track_to_playlist,
    create_playlist,
    delete_playlist,
    get_connection,
    get_playlist,
    get_playlist_tracks,
    list_playlists,
    remove_track_from_playlist,
    reorder_playlist_tracks,
)
from app.schemas import (
    AddTrackIn,
    CreatePlaylistIn,
    PlaylistDetailOut,
    PlaylistOut,
    ReorderIn,
)

router = APIRouter(dependencies=[Depends(require_api_key)])


def _playlist_track_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "track_no": row["track_no"],
        "duration_sec": row["duration_sec"],
        "album_id": row["album_id"],
        "bit_depth": row["bit_depth"],
        "sample_rate": row["sample_rate"],
        "size_bytes": row["size_bytes"],
        "artist_name": row["artist_name"],
        "album_title": row["album_title"],
    }


@router.get("/playlists", response_model=list[PlaylistOut])
def get_playlists():
    with get_connection() as conn:
        rows = list_playlists(conn)
    return [dict(r) for r in rows]


@router.post("/playlists", response_model=PlaylistOut)
def create_playlist_endpoint(body: CreatePlaylistIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Playlist name cannot be empty")
    with get_connection() as conn:
        try:
            playlist_id = create_playlist(conn, name)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A playlist with that name already exists")
    return {"id": playlist_id, "name": name, "track_count": 0}


@router.get("/playlists/{playlist_id}", response_model=PlaylistDetailOut)
def get_playlist_endpoint(playlist_id: int):
    with get_connection() as conn:
        playlist = get_playlist(conn, playlist_id)
        if not playlist:
            raise HTTPException(404, "Playlist not found")
        track_rows = get_playlist_tracks(conn, playlist_id)
    tracks = [_playlist_track_out(r) for r in track_rows]
    return {"id": playlist["id"], "name": playlist["name"], "track_count": len(tracks), "tracks": tracks}


@router.delete("/playlists/{playlist_id}")
def delete_playlist_endpoint(playlist_id: int):
    with get_connection() as conn:
        if not get_playlist(conn, playlist_id):
            raise HTTPException(404, "Playlist not found")
        delete_playlist(conn, playlist_id)
    return {"status": "deleted"}


@router.post("/playlists/{playlist_id}/tracks")
def add_track_endpoint(playlist_id: int, body: AddTrackIn):
    with get_connection() as conn:
        if not get_playlist(conn, playlist_id):
            raise HTTPException(404, "Playlist not found")
        track_exists = conn.execute(
            "SELECT 1 FROM tracks WHERE id = ?", (body.track_id,)
        ).fetchone()
        if not track_exists:
            raise HTTPException(404, "Track not found")
        add_track_to_playlist(conn, playlist_id, body.track_id)
    return {"status": "added"}


@router.delete("/playlists/{playlist_id}/tracks/{track_id}")
def remove_track_endpoint(playlist_id: int, track_id: int):
    with get_connection() as conn:
        if not get_playlist(conn, playlist_id):
            raise HTTPException(404, "Playlist not found")
        remove_track_from_playlist(conn, playlist_id, track_id)
    return {"status": "removed"}


@router.put("/playlists/{playlist_id}/order")
def reorder_endpoint(playlist_id: int, body: ReorderIn):
    with get_connection() as conn:
        if not get_playlist(conn, playlist_id):
            raise HTTPException(404, "Playlist not found")
        reorder_playlist_tracks(conn, playlist_id, body.track_ids)
    return {"status": "reordered"}
