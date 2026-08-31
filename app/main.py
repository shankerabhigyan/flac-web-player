from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import catalog, playlists, stream, subsonic, upload
from app.subsonic_auth import SUBSONIC_API_VERSION, SubsonicError

STATIC_DIR = Path(__file__).resolve().parent / "static"

init_db()

app = FastAPI(title="Abhigyan's FLAC Player")
app.include_router(catalog.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(subsonic.router)  # already namespaced under /rest, no collision with SPA routes
app.include_router(upload.router, prefix="/api")
app.include_router(playlists.router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.exception_handler(SubsonicError)
async def handle_subsonic_error(request: Request, exc: SubsonicError) -> JSONResponse:
    return JSONResponse(
        {
            "subsonic-response": {
                "status": "failed",
                "version": SUBSONIC_API_VERSION,
                "error": {"code": exc.code, "message": exc.message},
            }
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# SPA catch-all: any GET not matched by an API/static/health/subsonic route above is a
# client-side route (e.g. /playlists, /albums/5) — serve the app shell and let app.js's
# router read location.pathname. Must stay registered last so it never shadows a real route.
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8123, reload=True)
