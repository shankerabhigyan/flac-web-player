from app.db import get_connection, get_or_create_album, get_or_create_artist, insert_track


def _seed_track():
    with get_connection() as conn:
        artist_id = get_or_create_artist(conn, "Pink Floyd")
        album_id, _ = get_or_create_album(conn, artist_id, "The Dark Side of the Moon", 1973)
        track_id = insert_track(
            conn,
            album_id=album_id,
            title="Time",
            track_no=4,
            duration_sec=421.0,
            r2_key="pink-floyd/dark-side/04.flac",
            file_hash="hash-time",
            bit_depth=16,
            sample_rate=44100,
            size_bytes=9_000_000,
        )
    return artist_id, album_id, track_id


def test_artists_endpoint_requires_api_key(client):
    resp = client.get("/api/artists")
    assert resp.status_code == 401


def test_artists_endpoint_rejects_wrong_key(client):
    resp = client.get("/api/artists", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_artists_endpoint_lists_seeded_artist(client, auth_headers):
    _seed_track()
    resp = client.get("/api/artists", headers=auth_headers)
    assert resp.status_code == 200
    assert [a["name"] for a in resp.json()] == ["Pink Floyd"]


def test_album_detail_includes_tracks(client, auth_headers):
    _, album_id, _ = _seed_track()
    resp = client.get(f"/api/albums/{album_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "The Dark Side of the Moon"
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["title"] == "Time"


def test_album_detail_404_for_missing_album(client, auth_headers):
    resp = client.get("/api/albums/999", headers=auth_headers)
    assert resp.status_code == 404


def test_search_matches_across_tracks(client, auth_headers):
    _seed_track()
    resp = client.get("/api/search", params={"q": "Time"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["title"] == "Time"


def test_lyrics_endpoint_returns_null_when_not_embedded(client, auth_headers):
    _, _, track_id = _seed_track()
    resp = client.get(f"/api/tracks/{track_id}/lyrics", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"lyrics": None}


def test_recent_endpoint_empty_before_any_play(client, auth_headers):
    _seed_track()
    resp = client.get("/api/recent", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []
