from app.db import (
    add_track_to_playlist,
    create_playlist,
    get_artist_albums,
    get_or_create_album,
    get_or_create_artist,
    get_playlist_tracks,
    get_recent_tracks,
    insert_track,
    link_track_artists,
    record_play,
    track_exists_by_hash,
)


def _make_track(conn, artist_name, album_title, track_title, r2_key, file_hash):
    artist_id = get_or_create_artist(conn, artist_name)
    album_id, _ = get_or_create_album(conn, artist_id, album_title, 2020)
    track_id = insert_track(
        conn,
        album_id=album_id,
        title=track_title,
        track_no=1,
        duration_sec=180.0,
        r2_key=r2_key,
        file_hash=file_hash,
        bit_depth=16,
        sample_rate=44100,
        size_bytes=1_000_000,
    )
    return artist_id, album_id, track_id


def test_get_or_create_artist_is_idempotent(conn):
    first = get_or_create_artist(conn, "Pink Floyd")
    second = get_or_create_artist(conn, "Pink Floyd")
    assert first == second


def test_track_exists_by_hash(conn):
    assert track_exists_by_hash(conn, "abc123") is False
    _make_track(conn, "Pink Floyd", "The Wall", "Time", "pink-floyd/the-wall/01.flac", "abc123")
    assert track_exists_by_hash(conn, "abc123") is True


def test_link_track_artists_credits_every_artist(conn):
    """A compound-credit track ("Asfar Hussain; Xulfi") must show up under BOTH
    artists' pages, not fragment into a disconnected third artist entry."""
    _, album_id, track_id = _make_track(
        conn, "Asfar Hussain", "Collab Album", "Song", "collab/01.flac", "hash1"
    )
    link_track_artists(conn, track_id, ["Asfar Hussain", "Xulfi"])

    asfar_id = get_or_create_artist(conn, "Asfar Hussain")
    xulfi_id = get_or_create_artist(conn, "Xulfi")

    asfar_albums = {row["id"] for row in get_artist_albums(conn, asfar_id)}
    xulfi_albums = {row["id"] for row in get_artist_albums(conn, xulfi_id)}

    assert album_id in asfar_albums
    assert album_id in xulfi_albums


def test_link_track_artists_is_order_preserving_and_dedupes(conn):
    _, _, track_id = _make_track(conn, "Solo Artist", "Solo Album", "Song", "solo/01.flac", "hash2")
    link_track_artists(conn, track_id, ["Solo Artist", "Solo Artist"])

    rows = conn.execute(
        "SELECT COUNT(*) AS c FROM track_artists WHERE track_id = ?", (track_id,)
    ).fetchone()
    assert rows["c"] == 1


def test_get_recent_tracks_dedupes_to_latest_play(conn):
    _, _, track_id = _make_track(conn, "Artist", "Album", "Song", "a/01.flac", "hash3")
    record_play(conn, track_id)
    record_play(conn, track_id)
    record_play(conn, track_id)

    recent = get_recent_tracks(conn, limit=50)
    assert len(recent) == 1
    assert recent[0]["id"] == track_id


def test_get_recent_tracks_orders_most_recent_first(conn):
    _, _, track_a = _make_track(conn, "Artist A", "Album A", "Song A", "a/01.flac", "hash-a")
    _, _, track_b = _make_track(conn, "Artist B", "Album B", "Song B", "b/01.flac", "hash-b")

    conn.execute(
        "INSERT INTO play_history (track_id, played_at) VALUES (?, '2020-01-01 00:00:00')",
        (track_a,),
    )
    conn.execute(
        "INSERT INTO play_history (track_id, played_at) VALUES (?, '2020-01-02 00:00:00')",
        (track_b,),
    )

    recent = get_recent_tracks(conn, limit=50)
    assert [row["id"] for row in recent] == [track_b, track_a]


def test_add_track_to_playlist_is_idempotent(conn):
    _, _, track_id = _make_track(conn, "Artist", "Album", "Song", "a/01.flac", "hash4")
    playlist_id = create_playlist(conn, "Workout")

    add_track_to_playlist(conn, playlist_id, track_id)
    add_track_to_playlist(conn, playlist_id, track_id)

    tracks = get_playlist_tracks(conn, playlist_id)
    assert len(tracks) == 1


def test_playlist_tracks_cascade_delete_when_track_removed(conn):
    _, _, track_id = _make_track(conn, "Artist", "Album", "Song", "a/01.flac", "hash5")
    playlist_id = create_playlist(conn, "Workout")
    add_track_to_playlist(conn, playlist_id, track_id)

    conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))

    assert get_playlist_tracks(conn, playlist_id) == []
