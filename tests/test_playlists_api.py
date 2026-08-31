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


def test_create_and_list_playlist(client, auth_headers):
    resp = client.post("/api/playlists", json={"name": "Workout"}, headers=auth_headers)
    assert resp.status_code == 200
    playlist_id = resp.json()["id"]

    resp = client.get("/api/playlists", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == [{"id": playlist_id, "name": "Workout", "track_count": 0}]


def test_create_playlist_rejects_empty_name(client, auth_headers):
    resp = client.post("/api/playlists", json={"name": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_playlist_rejects_duplicate_name(client, auth_headers):
    client.post("/api/playlists", json={"name": "Workout"}, headers=auth_headers)
    resp = client.post("/api/playlists", json={"name": "Workout"}, headers=auth_headers)
    assert resp.status_code == 409


def test_add_and_remove_track(client, auth_headers):
    track_id = _seed_track()
    playlist_id = client.post(
        "/api/playlists", json={"name": "Workout"}, headers=auth_headers
    ).json()["id"]

    resp = client.post(
        f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id}, headers=auth_headers
    )
    assert resp.status_code == 200

    detail = client.get(f"/api/playlists/{playlist_id}", headers=auth_headers).json()
    assert detail["track_count"] == 1
    assert detail["tracks"][0]["id"] == track_id

    resp = client.delete(
        f"/api/playlists/{playlist_id}/tracks/{track_id}", headers=auth_headers
    )
    assert resp.status_code == 200

    detail = client.get(f"/api/playlists/{playlist_id}", headers=auth_headers).json()
    assert detail["track_count"] == 0


def test_add_track_404_for_missing_playlist(client, auth_headers):
    track_id = _seed_track()
    resp = client.post(
        "/api/playlists/999/tracks", json={"track_id": track_id}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_add_track_404_for_missing_track(client, auth_headers):
    playlist_id = client.post(
        "/api/playlists", json={"name": "Workout"}, headers=auth_headers
    ).json()["id"]
    resp = client.post(
        f"/api/playlists/{playlist_id}/tracks", json={"track_id": 999}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_delete_playlist(client, auth_headers):
    playlist_id = client.post(
        "/api/playlists", json={"name": "Workout"}, headers=auth_headers
    ).json()["id"]

    resp = client.delete(f"/api/playlists/{playlist_id}", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get(f"/api/playlists/{playlist_id}", headers=auth_headers)
    assert resp.status_code == 404
