"""Set a CORS policy on the R2 bucket so the browser's Web Audio API can read
frequency data from cross-origin presigned-URL audio (needed for the live
spectrum visualizer — plain <audio> playback works fine without this, but
tapping the stream into an AnalyserNode requires the response to carry CORS
headers). GET-only, no credentials — presigned URLs already handle auth via
their signature, so this doesn't loosen access to anything.

Re-run this after adding a new origin (e.g. once the app is deployed
somewhere other than localhost) to add it to ALLOWED_ORIGINS below.
"""

from app.config import get_settings
from app.storage import get_r2_client

ALLOWED_ORIGINS = [
    "http://127.0.0.1:8123",
    "http://localhost:8123",
]


def main() -> None:
    settings = get_settings()
    client = get_r2_client()

    client.put_bucket_cors(
        Bucket=settings.r2_bucket_name,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": ALLOWED_ORIGINS,
                    "AllowedMethods": ["GET"],
                    "AllowedHeaders": ["*"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )
    print(f"CORS policy set on {settings.r2_bucket_name} for origins: {ALLOWED_ORIGINS}")


if __name__ == "__main__":
    main()
