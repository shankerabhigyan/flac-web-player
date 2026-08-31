from app.db import (
    get_connection,
    get_or_create_album,
    get_or_create_artist,
    insert_track,
    link_track_artists,
    record_play,
)


def _seed_collab_track():
    """A track credited to two artists, played twice — exercises both the
    per-artist attribution (both should get credit) and the play-count grouping."""
    with get_connection() as conn:
        artist_id = get_or_create_artist(conn, "Asfar Hussain")
        album_id, _ = get_or_create_album(conn, artist_id, "Collab Album", 2020)
        track_id = insert_track(
            conn,
            album_id=album_id,
            title="Duet",
            track_no=1,
            duration_sec=200.0,
            r2_key="collab/01.flac",
            file_hash="hash-duet",
            bit_depth=16,
            sample_rate=44100,
            size_bytes=5_000_000,
        )
        link_track_artists(conn, track_id, ["Asfar Hussain", "Xulfi"])
        record_play(conn, track_id)
        record_play(conn, track_id)
    return track_id


def test_stats_requires_api_key(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 401


def test_stats_empty_before_any_plays(client, auth_headers):
    resp = client.get("/api/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_plays"] == 0
    assert body["unique_tracks"] == 0
    assert body["total_hours"] == 0
    assert body["top_artists"] == []
    assert body["top_tracks"] == []
    assert body["play_timestamps"] == []


def test_stats_summary_counts_plays_and_hours(client, auth_headers):
    _seed_collab_track()
    resp = client.get("/api/stats", headers=auth_headers)
    body = resp.json()
    assert body["total_plays"] == 2
    assert body["unique_tracks"] == 1
    assert body["total_hours"] == round(2 * 200.0 / 3600, 1)
    assert len(body["play_timestamps"]) == 2


def test_stats_top_artists_credits_every_collaborator(client, auth_headers):
    """A collab track's plays must count toward BOTH credited artists, not just
    the album's display artist — same philosophy as get_artist_albums."""
    _seed_collab_track()
    resp = client.get("/api/stats", headers=auth_headers)
    body = resp.json()
    names = {a["name"]: a["play_count"] for a in body["top_artists"]}
    assert names == {"Asfar Hussain": 2, "Xulfi": 2}


def test_stats_top_tracks_reports_play_count(client, auth_headers):
    track_id = _seed_collab_track()
    resp = client.get("/api/stats", headers=auth_headers)
    body = resp.json()
    assert len(body["top_tracks"]) == 1
    assert body["top_tracks"][0]["id"] == track_id
    assert body["top_tracks"][0]["play_count"] == 2
    assert body["top_tracks"][0]["artist_name"] == "Asfar Hussain"
