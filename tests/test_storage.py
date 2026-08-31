from app import storage


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.calls.append((operation, Params, ExpiresIn))
        return f"https://fake-r2.example/{Params['Bucket']}/{Params['Key']}?ttl={ExpiresIn}"


def test_presigned_get_url_builds_expected_request(monkeypatch):
    fake_client = FakeS3Client()
    monkeypatch.setattr(storage, "get_r2_client", lambda: fake_client)

    url = storage.presigned_get_url("artist/album/01.flac", expires_in=120)

    assert url == "https://fake-r2.example/test-bucket/artist/album/01.flac?ttl=120"
    operation, params, ttl = fake_client.calls[0]
    assert operation == "get_object"
    assert params == {"Bucket": "test-bucket", "Key": "artist/album/01.flac"}
    assert ttl == 120


def test_presigned_get_url_defaults_to_one_hour(monkeypatch):
    fake_client = FakeS3Client()
    monkeypatch.setattr(storage, "get_r2_client", lambda: fake_client)

    storage.presigned_get_url("some/key.flac")

    _, _, ttl = fake_client.calls[0]
    assert ttl == 3600
