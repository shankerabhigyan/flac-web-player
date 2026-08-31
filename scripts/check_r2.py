"""Phase 0 sanity check: confirm boto3 can list/put/get against the R2 bucket."""

from app.config import get_settings
from app.storage import get_r2_client


def main() -> None:
    settings = get_settings()
    client = get_r2_client()

    print(f"Bucket: {settings.r2_bucket_name}")
    print(f"Endpoint: {settings.r2_endpoint_url}")

    client.put_object(Bucket=settings.r2_bucket_name, Key="_healthcheck.txt", Body=b"ok")
    print("PUT ok")

    obj = client.get_object(Bucket=settings.r2_bucket_name, Key="_healthcheck.txt")
    body = obj["Body"].read()
    assert body == b"ok", f"unexpected body: {body!r}"
    print("GET ok")

    resp = client.list_objects_v2(Bucket=settings.r2_bucket_name)
    keys = [o["Key"] for o in resp.get("Contents", [])]
    print(f"LIST ok, {len(keys)} object(s): {keys}")

    client.delete_object(Bucket=settings.r2_bucket_name, Key="_healthcheck.txt")
    print("DELETE ok — R2 connectivity confirmed.")


if __name__ == "__main__":
    main()
