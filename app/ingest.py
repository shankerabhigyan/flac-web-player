"""Shared ingestion logic: tag-extract a local FLAC, upload to R2, upsert the catalog.

Used by both scripts/ingest.py (CLI, walks a directory) and app/routers/upload.py (API,
one file at a time from a web upload) so both paths share identical behavior.
"""

import hashlib
from pathlib import Path

from app.db import (
    get_or_create_album,
    get_or_create_artist,
    insert_track,
    link_track_artists,
    set_album_cover,
    track_exists_by_hash,
)
from app.tags import TrackTags, read_flac_tags, sanitize_path_component

COVER_MIME_EXT = {"image/jpeg": "jpg", "image/png": "png"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_track_key(tags: TrackTags) -> str:
    artist = sanitize_path_component(tags.artists[0])
    album = sanitize_path_component(tags.album)
    title = sanitize_path_component(tags.title)
    track_no = f"{tags.track_no:02d} - " if tags.track_no else ""
    return f"{artist}/{album}/{track_no}{title}.flac"


def build_cover_key(tags: TrackTags, mime: str) -> str:
    artist = sanitize_path_component(tags.artists[0])
    album = sanitize_path_component(tags.album)
    ext = COVER_MIME_EXT.get(mime, "jpg")
    return f"{artist}/{album}/cover.{ext}"


def ingest_file(path: Path, conn, client, bucket: str) -> dict:
    """Ingest one local FLAC file. Returns {"status": "uploaded"|"skipped", "track_id", "r2_key"}.

    Raises on bad tags (ValueError) or any upload/DB failure — the caller decides how to
    report/collect errors, since the CLI and the API want different error handling.
    """
    file_hash = sha256_of(path)
    if track_exists_by_hash(conn, file_hash):
        return {"status": "skipped", "track_id": None, "r2_key": None}

    tags = read_flac_tags(path)
    artist_id = get_or_create_artist(conn, tags.artists[0])
    album_id, existing_cover_key = get_or_create_album(conn, artist_id, tags.album, tags.year)

    r2_key = build_track_key(tags)
    client.upload_file(str(path), bucket, r2_key)

    if not existing_cover_key and tags.cover:
        cover_data, cover_mime = tags.cover
        cover_key = build_cover_key(tags, cover_mime)
        client.put_object(Bucket=bucket, Key=cover_key, Body=cover_data, ContentType=cover_mime)
        set_album_cover(conn, album_id, cover_key)

    track_id = insert_track(
        conn,
        album_id=album_id,
        title=tags.title,
        track_no=tags.track_no,
        duration_sec=tags.duration_sec,
        r2_key=r2_key,
        file_hash=file_hash,
        bit_depth=tags.bit_depth,
        sample_rate=tags.sample_rate,
        size_bytes=path.stat().st_size,
        lyrics=tags.lyrics,
    )
    link_track_artists(conn, track_id, tags.artists)
    return {"status": "uploaded", "track_id": track_id, "r2_key": r2_key}
