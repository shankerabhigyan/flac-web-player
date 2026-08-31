import hashlib

import pytest

from app.subsonic_auth import SubsonicError, require_subsonic_auth


def test_plain_password_auth_succeeds():
    require_subsonic_auth(u="testuser", p="testpass", t=None, s=None)


def test_wrong_username_rejected():
    with pytest.raises(SubsonicError) as exc:
        require_subsonic_auth(u="nope", p="testpass", t=None, s=None)
    assert exc.value.code == 40


def test_wrong_password_rejected():
    with pytest.raises(SubsonicError) as exc:
        require_subsonic_auth(u="testuser", p="wrong", t=None, s=None)
    assert exc.value.code == 40


def test_hex_encoded_password_is_decoded():
    encoded = "enc:" + "testpass".encode("utf-8").hex()
    require_subsonic_auth(u="testuser", p=encoded, t=None, s=None)


def test_token_auth_succeeds_with_correct_salt():
    salt = "abc123"
    token = hashlib.md5(("testpass" + salt).encode("utf-8")).hexdigest()
    require_subsonic_auth(u="testuser", p=None, t=token, s=salt)


def test_token_auth_rejects_wrong_token():
    with pytest.raises(SubsonicError) as exc:
        require_subsonic_auth(u="testuser", p=None, t="deadbeef", s="abc123")
    assert exc.value.code == 40


def test_missing_credentials_raises_required_parameter_error():
    with pytest.raises(SubsonicError) as exc:
        require_subsonic_auth(u="testuser", p=None, t=None, s=None)
    assert exc.value.code == 10


def test_ping_endpoint_requires_auth(client):
    resp = client.get("/rest/ping.view", params={"u": "testuser", "p": "wrongpass", "f": "json"})
    body = resp.json()
    assert body["subsonic-response"]["status"] == "failed"
    assert body["subsonic-response"]["error"]["code"] == 40


def test_ping_endpoint_succeeds_with_correct_credentials(client):
    resp = client.get("/rest/ping.view", params={"u": "testuser", "p": "testpass", "f": "json"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subsonic-response"]["status"] == "ok"
