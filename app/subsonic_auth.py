import hashlib

from fastapi import Query

from app.config import get_settings

SUBSONIC_API_VERSION = "1.16.1"


class SubsonicError(Exception):
    """Raised by a Subsonic route handler; rendered as a subsonic-response error envelope."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


def _decode_password(p: str) -> str:
    if p.startswith("enc:"):
        return bytes.fromhex(p[4:]).decode("utf-8")
    return p


def require_subsonic_auth(
    u: str = Query(...),
    p: str | None = Query(default=None),
    t: str | None = Query(default=None),
    s: str | None = Query(default=None),
) -> None:
    settings = get_settings()

    if u != settings.subsonic_username:
        raise SubsonicError(40, "Wrong username or password.")

    if t is not None and s is not None:
        expected = hashlib.md5((settings.subsonic_password + s).encode("utf-8")).hexdigest()
        if t.lower() == expected:
            return
        raise SubsonicError(40, "Wrong username or password.")

    if p is not None:
        if _decode_password(p) == settings.subsonic_password:
            return
        raise SubsonicError(40, "Wrong username or password.")

    raise SubsonicError(10, "Required parameter is missing.")
