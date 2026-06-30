def test_put_get_roundtrip(s3):
    from app.storage import put_archive, get_archive
    put_archive("a/v1.tar.gz", b"hello-bytes")
    assert get_archive("a/v1.tar.gz") == b"hello-bytes"

def test_presign_returns_url(s3):
    from app.storage import put_archive, presign_get
    put_archive("a/v1.tar.gz", b"x")
    url = presign_get("a/v1.tar.gz")
    assert url.startswith("http") and "a/v1.tar.gz" in url
