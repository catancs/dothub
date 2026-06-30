def test_put_get_roundtrip(s3):
    from app.storage import put_archive, get_archive
    put_archive("a/v1.tar.gz", b"hello-bytes")
    assert get_archive("a/v1.tar.gz") == b"hello-bytes"

def test_presign_returns_url(s3):
    from app.storage import put_archive, presign_get
    put_archive("a/v1.tar.gz", b"x")
    url = presign_get("a/v1.tar.gz")
    assert url.startswith("http") and "a/v1.tar.gz" in url

def test_local_disk_backend_roundtrip(tmp_path, monkeypatch):
    # No S3/moto: with STORAGE_DIR set, bundles round-trip through the local dir.
    from app import storage
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))
    storage.put_archive("b/v1.tar.gz", b"local-bytes")
    assert (tmp_path / "b" / "v1.tar.gz").read_bytes() == b"local-bytes"
    assert storage.get_archive("b/v1.tar.gz") == b"local-bytes"
    assert storage.presign_get("b/v1.tar.gz").startswith("file://")
