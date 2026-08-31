import sqlite3

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.db import get_connection, record_play
from app.storage import presigned_get_url
from app.subsonic_auth import SUBSONIC_API_VERSION, SubsonicError, require_subsonic_auth

router = APIRouter(prefix="/rest", dependencies=[Depends(require_subsonic_auth)])

_ALBUM_SELECT = """
    SELECT albums.id, albums.title, albums.year, albums.artist_id, albums.cover_art_key,
           artists.name AS artist_name,
           COUNT(tracks.id) AS song_count, COALESCE(SUM(tracks.duration_sec), 0) AS total_duration
    FROM albums
    JOIN artists ON artists.id = albums.artist_id
    LEFT JOIN tracks ON tracks.album_id = albums.id
"""


def envelope(payload: dict | None = None) -> dict:
    body = {
        "status": "ok",
        "version": SUBSONIC_API_VERSION,
        "type": "abhigyans-flac-player",
        "serverVersion": "0.1.0",
    }
    if payload:
        body.update(payload)
    return {"subsonic-response": body}


def _album_summary(row: sqlite3.Row) -> dict:
    out = {
        "id": str(row["id"]),
        "name": row["title"],
        "artist": row["artist_name"],
        "artistId": str(row["artist_id"]),
        "coverArt": f"al-{row['id']}" if row["cover_art_key"] else None,
        "year": row["year"],
        "songCount": row["song_count"],
        "duration": round(row["total_duration"]),
    }
    return {k: v for k, v in out.items() if v is not None}


def _song(row: sqlite3.Row, album_title: str, artist_name: str, artist_id: int) -> dict:
    bit_rate = None
    if row["size_bytes"] and row["duration_sec"]:
        bit_rate = round(row["size_bytes"] * 8 / row["duration_sec"] / 1000)
    out = {
        "id": str(row["id"]),
        "parent": str(row["album_id"]),
        "isDir": False,
        "title": row["title"],
        "album": album_title,
        "artist": artist_name,
        "track": row["track_no"],
        "duration": round(row["duration_sec"]) if row["duration_sec"] else None,
        "bitRate": bit_rate,
        "size": row["size_bytes"],
        "suffix": "flac",
        "contentType": "audio/flac",
        "coverArt": f"al-{row['album_id']}",
        "type": "music",
        "albumId": str(row["album_id"]),
        "artistId": str(artist_id),
    }
    return {k: v for k, v in out.items() if v is not None}


@router.get("/ping")
@router.get("/ping.view")
def ping():
    return envelope()


@router.get("/getLicense")
@router.get("/getLicense.view")
def get_license():
    return envelope({"license": {"valid": True}})


@router.get("/getArtists")
@router.get("/getArtists.view")
def get_artists():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT artists.id, artists.name, COUNT(albums.id) AS album_count
            FROM artists LEFT JOIN albums ON albums.artist_id = artists.id
            GROUP BY artists.id
            ORDER BY artists.name COLLATE NOCASE
            """
        ).fetchall()

    groups: dict[str, list[dict]] = {}
    for row in rows:
        letter = row["name"][:1].upper() if row["name"] else "?"
        groups.setdefault(letter, []).append(
            {"id": str(row["id"]), "name": row["name"], "albumCount": row["album_count"]}
        )

    index = [{"name": letter, "artist": artists} for letter, artists in sorted(groups.items())]
    return envelope({"artists": {"ignoredArticles": "", "index": index}})


@router.get("/getArtist")
@router.get("/getArtist.view")
def get_artist(id: str = Query(...)):
    artist_id = int(id)
    with get_connection() as conn:
        artist = conn.execute(
            "SELECT id, name FROM artists WHERE id = ?", (artist_id,)
        ).fetchone()
        if not artist:
            raise SubsonicError(70, "Artist not found")
        album_rows = conn.execute(
            f"""
            {_ALBUM_SELECT}
            WHERE albums.id IN (
                SELECT tracks.album_id FROM tracks
                JOIN track_artists ON track_artists.track_id = tracks.id
                WHERE track_artists.artist_id = ?
            )
            GROUP BY albums.id ORDER BY albums.year, albums.title
            """,
            (artist_id,),
        ).fetchall()

    albums = [_album_summary(r) for r in album_rows]
    return envelope(
        {
            "artist": {
                "id": str(artist["id"]),
                "name": artist["name"],
                "albumCount": len(albums),
                "album": albums,
            }
        }
    )


@router.get("/getAlbumList2")
@router.get("/getAlbumList2.view")
def get_album_list2(
    type: str = Query(default="alphabeticalByName", alias="type"),
    size: int = Query(default=50, le=500),
    offset: int = Query(default=0),
):
    order_by = "albums.title COLLATE NOCASE"
    if type == "newest":
        order_by = "albums.id DESC"
    elif type == "alphabeticalByArtist":
        order_by = "artists.name COLLATE NOCASE, albums.title COLLATE NOCASE"
    elif type == "random":
        order_by = "RANDOM()"

    with get_connection() as conn:
        rows = conn.execute(
            f"{_ALBUM_SELECT} GROUP BY albums.id ORDER BY {order_by} LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()

    return envelope({"albumList2": {"album": [_album_summary(r) for r in rows]}})


@router.get("/getAlbum")
@router.get("/getAlbum.view")
def get_album(id: str = Query(...)):
    album_id = int(id)
    with get_connection() as conn:
        row = conn.execute(
            f"{_ALBUM_SELECT} WHERE albums.id = ? GROUP BY albums.id", (album_id,)
        ).fetchone()
        if not row:
            raise SubsonicError(70, "Album not found")
        track_rows = conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? ORDER BY track_no", (album_id,)
        ).fetchall()

    album = _album_summary(row)
    album["song"] = [
        _song(t, row["title"], row["artist_name"], row["artist_id"]) for t in track_rows
    ]
    return envelope({"album": album})


@router.get("/search3")
@router.get("/search3.view")
def search3(query: str = Query(default="")):
    like = f"%{query}%"
    with get_connection() as conn:
        artist_rows = conn.execute(
            """
            SELECT artists.id, artists.name, COUNT(albums.id) AS album_count
            FROM artists LEFT JOIN albums ON albums.artist_id = artists.id
            WHERE artists.name LIKE ?
            GROUP BY artists.id ORDER BY artists.name COLLATE NOCASE LIMIT 25
            """,
            (like,),
        ).fetchall()
        album_rows = conn.execute(
            f"{_ALBUM_SELECT} WHERE albums.title LIKE ? "
            "GROUP BY albums.id ORDER BY albums.title COLLATE NOCASE LIMIT 25",
            (like,),
        ).fetchall()
        song_rows = conn.execute(
            """
            SELECT tracks.*, albums.title AS album_title, albums.artist_id AS album_artist_id,
                   artists.name AS artist_name
            FROM tracks
            JOIN albums ON albums.id = tracks.album_id
            JOIN artists ON artists.id = albums.artist_id
            WHERE tracks.title LIKE ?
            ORDER BY tracks.title COLLATE NOCASE LIMIT 25
            """,
            (like,),
        ).fetchall()

    artists = [
        {"id": str(r["id"]), "name": r["name"], "albumCount": r["album_count"]}
        for r in artist_rows
    ]
    albums = [_album_summary(r) for r in album_rows]
    songs = [_song(r, r["album_title"], r["artist_name"], r["album_artist_id"]) for r in song_rows]

    return envelope({"searchResult3": {"artist": artists, "album": albums, "song": songs}})


@router.get("/stream")
@router.get("/stream.view")
def stream(id: str = Query(...)):
    track_id = int(id)
    with get_connection() as conn:
        row = conn.execute("SELECT r2_key FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not row:
            raise SubsonicError(70, "Song not found")
        record_play(conn, track_id)
    url = presigned_get_url(row["r2_key"], expires_in=3600)
    return RedirectResponse(url, status_code=302)


@router.get("/getCoverArt")
@router.get("/getCoverArt.view")
def get_cover_art(id: str = Query(...)):
    if not id.startswith("al-"):
        raise SubsonicError(70, "Cover art not found")
    album_id = int(id[len("al-") :])
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cover_art_key FROM albums WHERE id = ?", (album_id,)
        ).fetchone()
    if not row or not row["cover_art_key"]:
        raise SubsonicError(70, "Cover art not found")
    url = presigned_get_url(row["cover_art_key"], expires_in=3600)
    return RedirectResponse(url, status_code=302)
