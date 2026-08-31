from app.db import get_connection, get_or_create_album, get_or_create_artist, insert_track


def _seed_track():
    with get_connection() as conn:
        artist_id = get_or_create_artist(conn, "Artist")
        album_id, _ = get_or_create_album(conn, artist_id, "Album", 2020)
        track_id = insert_track(
            conn,
            album_id=album_id,
            title="Song",
            track_no=1,
            duration_sec=200.0,
            r2_key="artist/album/01.flac",
            file_hash="hash-song",
            bit_depth=16,
            sample_rate=44100,
            size_bytes=5_000_000,
        )
    return track_id


def test_stream_returns_presigned_url_and_logs_play(client, auth_headers, monkeypatch):
    track_id = _seed_track()
    monkeypatch.setattr(
        "app.routers.stream.presigned_get_url",
        lambda key, expires_in=3600: f"https://fake-r2/{key}?sig=abc",
    )

    resp = client.get(f"/api/stream/{track_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://fake-r2/artist/album/01.flac?sig=abc"
    assert body["expires_in"] == 3600

    recent = client.get("/api/recent", headers=auth_headers).json()
    assert len(recent) == 1
    assert recent[0]["id"] == track_id


def test_stream_404_for_missing_track_and_does_not_log(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.routers.stream.presigned_get_url",
        lambda key, expires_in=3600: "should-not-be-called",
    )

    resp = client.get("/api/stream/999", headers=auth_headers)
    assert resp.status_code == 404

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM play_history").fetchone()["c"]
    assert count == 0


def test_cover_404_when_no_cover_art(client, auth_headers):
    with get_connection() as conn:
        artist_id = get_or_create_artist(conn, "Artist")
        album_id, _ = get_or_create_album(conn, artist_id, "Album", 2020)

    resp = client.get(f"/api/cover/{album_id}", headers=auth_headers)
    assert resp.status_code == 404
