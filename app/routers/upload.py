import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile

from app.auth import require_api_key
from app.config import get_settings
from app.db import get_connection
from app.ingest import ingest_file
from app.schemas import UploadResultOut
from app.storage import get_r2_client

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/upload", response_model=UploadResultOut)
async def upload_tracks(files: list[UploadFile]):
    settings = get_settings()
    client = get_r2_client()

    uploaded = []
    skipped = []
    failed = []

    with get_connection() as conn:
        for upload in files:
            if not (upload.filename or "").lower().endswith(".flac"):
                failed.append({"filename": upload.filename or "?", "error": "not a .flac file"})
                continue

            with tempfile.NamedTemporaryFile(suffix=".flac") as tmp:
                tmp.write(await upload.read())
                tmp.flush()

                try:
                    result = ingest_file(Path(tmp.name), conn, client, settings.r2_bucket_name)
                except Exception as exc:  # noqa: BLE001 - report and keep processing the rest
                    failed.append({"filename": upload.filename, "error": str(exc)})
                    continue

                if result["status"] == "uploaded":
                    uploaded.append({"filename": upload.filename, "r2_key": result["r2_key"]})
                else:
                    skipped.append(upload.filename)

    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}
