from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.db import get_connection, record_play
from app.schemas import StreamUrlOut
from app.storage import presigned_get_url

router = APIRouter(dependencies=[Depends(require_api_key)])

STREAM_URL_TTL = 3600
COVER_URL_TTL = 3600


@router.get("/stream/{track_id}", response_model=StreamUrlOut)
def stream_track(track_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT r2_key FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Track not found")
        record_play(conn, track_id)
    url = presigned_get_url(row["r2_key"], expires_in=STREAM_URL_TTL)
    return {"url": url, "expires_in": STREAM_URL_TTL}


@router.get("/cover/{album_id}", response_model=StreamUrlOut)
def album_cover(album_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cover_art_key FROM albums WHERE id = ?", (album_id,)
        ).fetchone()
    if not row or not row["cover_art_key"]:
        raise HTTPException(404, "Cover not found")
    url = presigned_get_url(row["cover_art_key"], expires_in=COVER_URL_TTL)
    return {"url": url, "expires_in": COVER_URL_TTL}
