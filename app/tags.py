import re
from dataclasses import dataclass
from pathlib import Path

from mutagen.flac import FLAC, Picture

ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')


@dataclass
class TrackTags:
    artists: list[str]  # ordered, primary/first-credited artist first
    album: str
    title: str
    track_no: int | None
    year: int | None
    duration_sec: float
    bit_depth: int | None
    sample_rate: int
    cover: tuple[bytes, str] | None  # (data, mime)
    lyrics: str | None


def _first(flac: FLAC, key: str) -> str | None:
    values = flac.get(key)
    return values[0].strip() if values else None


def _parse_artist_names(flac: FLAC) -> list[str]:
    """Split a compound 'artist' tag (e.g. "Asfar Hussain; Xulfi") into individual
    names, also handling files that store genuinely repeated ARTIST fields (mutagen
    then returns multiple list values already). Order is preserved and de-duplicated
    so the first name is always the primary/first-credited artist."""
    names: list[str] = []
    for value in flac.get("artist") or []:
        for part in value.split(";"):
            part = part.strip()
            if part:
                names.append(part)

    seen: set[str] = set()
    result = []
    for name in names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _parse_track_no(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.match(r"\d+", raw)
    return int(match.group()) if match else None


def _parse_year(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.match(r"\d{4}", raw)
    return int(match.group()) if match else None


def _extract_cover(flac: FLAC) -> tuple[bytes, str] | None:
    pictures: list[Picture] = flac.pictures
    if not pictures:
        return None
    # type 3 = front cover; fall back to the first embedded picture
    picture = next((p for p in pictures if p.type == 3), pictures[0])
    return picture.data, picture.mime


def read_flac_tags(path: Path) -> TrackTags:
    flac = FLAC(path)

    artists = _parse_artist_names(flac)
    album = _first(flac, "album")
    title = _first(flac, "title")
    if not artists or not album or not title:
        raise ValueError(f"missing artist/album/title tag(s) in {path}")

    return TrackTags(
        artists=artists,
        album=album,
        title=title,
        track_no=_parse_track_no(_first(flac, "tracknumber")),
        year=_parse_year(_first(flac, "date")),
        duration_sec=flac.info.length,
        bit_depth=flac.info.bits_per_sample,
        sample_rate=flac.info.sample_rate,
        cover=_extract_cover(flac),
        lyrics=_first(flac, "lyrics"),
    )


def sanitize_path_component(value: str) -> str:
    cleaned = ILLEGAL_CHARS.sub("-", value).strip().strip(".")
    return cleaned or "unknown"
