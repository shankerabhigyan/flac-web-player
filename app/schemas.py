from pydantic import BaseModel


class ArtistOut(BaseModel):
    id: int
    name: str


class AlbumOut(BaseModel):
    id: int
    title: str
    year: int | None
    artist_id: int
    artist_name: str
    has_cover: bool


class TrackOut(BaseModel):
    id: int
    title: str
    track_no: int | None
    duration_sec: float | None
    album_id: int
    bit_depth: int | None
    sample_rate: int | None
    size_bytes: int | None


class AlbumDetailOut(AlbumOut):
    tracks: list[TrackOut]


class SearchOut(BaseModel):
    artists: list[ArtistOut]
    albums: list[AlbumOut]
    tracks: list[TrackOut]


class StreamUrlOut(BaseModel):
    url: str
    expires_in: int


class UploadedFileOut(BaseModel):
    filename: str
    r2_key: str


class FailedUploadOut(BaseModel):
    filename: str
    error: str


class UploadResultOut(BaseModel):
    uploaded: list[UploadedFileOut]
    skipped: list[str]
    failed: list[FailedUploadOut]


class PlaylistOut(BaseModel):
    id: int
    name: str
    track_count: int


class PlaylistTrackOut(TrackOut):
    artist_name: str
    album_title: str


class PlaylistDetailOut(PlaylistOut):
    tracks: list[PlaylistTrackOut]


class CreatePlaylistIn(BaseModel):
    name: str


class AddTrackIn(BaseModel):
    track_id: int


class ReorderIn(BaseModel):
    track_ids: list[int]


class TrackLyricsOut(BaseModel):
    lyrics: str | None


class RecentTrackOut(TrackOut):
    artist_name: str
    album_title: str
    played_at: str


class TopArtistOut(BaseModel):
    id: int
    name: str
    play_count: int


class TopTrackOut(BaseModel):
    id: int
    title: str
    artist_name: str
    album_title: str
    play_count: int


class StatsOut(BaseModel):
    total_plays: int
    unique_tracks: int
    total_hours: float
    top_artists: list[TopArtistOut]
    top_tracks: list[TopTrackOut]
    play_timestamps: list[str]
