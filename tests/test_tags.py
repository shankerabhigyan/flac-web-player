from app.tags import (
    _parse_artist_names,
    _parse_track_no,
    _parse_year,
    sanitize_path_component,
)


def test_parse_artist_names_splits_compound_tag():
    flac = {"artist": ["Asfar Hussain; Xulfi"]}
    assert _parse_artist_names(flac) == ["Asfar Hussain", "Xulfi"]


def test_parse_artist_names_dedupes_repeated_values():
    flac = {"artist": ["Pink Floyd", "Pink Floyd"]}
    assert _parse_artist_names(flac) == ["Pink Floyd"]


def test_parse_artist_names_handles_missing_tag():
    assert _parse_artist_names({}) == []


def test_parse_artist_names_strips_whitespace_around_separators():
    flac = {"artist": ["  Asfar Hussain ;  Xulfi  "]}
    assert _parse_artist_names(flac) == ["Asfar Hussain", "Xulfi"]


def test_parse_artist_names_preserves_primary_order():
    flac = {"artist": ["Xulfi; Asfar Hussain"]}
    assert _parse_artist_names(flac) == ["Xulfi", "Asfar Hussain"]


def test_parse_track_no_extracts_leading_digits():
    assert _parse_track_no("7/12") == 7


def test_parse_track_no_handles_missing_value():
    assert _parse_track_no(None) is None
    assert _parse_track_no("") is None


def test_parse_year_extracts_four_digit_year():
    assert _parse_year("2011-05-01") == 2011


def test_parse_year_handles_missing_value():
    assert _parse_year(None) is None


def test_sanitize_path_component_replaces_illegal_chars():
    assert sanitize_path_component('AC/DC: Back?') == "AC-DC- Back-"


def test_sanitize_path_component_falls_back_when_empty():
    assert sanitize_path_component("...") == "unknown"
