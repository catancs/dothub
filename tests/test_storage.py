def test_put_get_roundtrip(s3):
    from app.storage import put_archive, get_archive
    put_archive("a/v1.tar.gz", b"hello-bytes")
    assert get_archive("a/v1.tar.gz") == b"hello-bytes"

def test_local_disk_backend_roundtrip(tmp_path, monkeypatch):
    # No S3/moto: with STORAGE_DIR set, bundles round-trip through the local dir.
    from app import storage
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))
    storage.put_archive("b/v1.tar.gz", b"local-bytes")
    assert (tmp_path / "b" / "v1.tar.gz").read_bytes() == b"local-bytes"
    assert storage.get_archive("b/v1.tar.gz") == b"local-bytes"


def test_encrypts_at_rest_when_key_set(tmp_path, monkeypatch):
    # With STORAGE_ENCRYPTION_KEY set, on-disk bytes are ciphertext but the
    # round-trip returns the original plaintext.
    from cryptography.fernet import Fernet
    from app import storage
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(storage.settings, "storage_encryption_key", Fernet.generate_key().decode())
    storage.put_archive("c/v1.tar.gz", b"secret-bundle-bytes")
    on_disk = (tmp_path / "c" / "v1.tar.gz").read_bytes()
    assert b"secret-bundle-bytes" not in on_disk
    assert storage.get_archive("c/v1.tar.gz") == b"secret-bundle-bytes"
