"""Phase 1: walk a local FLAC library, extract tags, upload to R2, populate SQLite catalog.

Idempotent — safe to re-run on a growing library. Tracks are deduped by content hash (sha256),
so a renamed/moved local file is recognized as already-ingested rather than re-uploaded.

Usage:
    python -m scripts.ingest /path/to/flac/library
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db import get_connection, init_db
from app.ingest import ingest_file
from app.storage import get_r2_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library_path", type=Path, help="root directory of FLAC files")
    args = parser.parse_args()

    if not args.library_path.is_dir():
        print(f"Not a directory: {args.library_path}", file=sys.stderr)
        sys.exit(1)

    init_db()
    settings = get_settings()
    client = get_r2_client()

    flac_files = sorted(args.library_path.rglob("*.flac"))
    print(f"Found {len(flac_files)} .flac file(s) under {args.library_path}")

    uploaded = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    with get_connection() as conn:
        for i, path in enumerate(flac_files, start=1):
            try:
                result = ingest_file(path, conn, client, settings.r2_bucket_name)
                if result["status"] == "uploaded":
                    uploaded += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 - log and continue ingesting the rest
                failed.append((str(path), str(exc)))
            if i % 50 == 0:
                print(f"  ... {i}/{len(flac_files)} processed")

    print()
    print(f"Uploaded: {uploaded}")
    print(f"Skipped (already ingested): {skipped}")
    print(f"Failed: {len(failed)}")
    for path, err in failed:
        print(f"  FAILED {path}: {err}")


if __name__ == "__main__":
    main()
