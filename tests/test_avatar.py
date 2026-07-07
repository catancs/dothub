import base64

from sqlalchemy import select

# A valid 1x1 PNG (real header: \x89PNG...), used for the happy-path upload.
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

PASSWORD = "Testpass123"  # >=10 chars incl. upper/lower/digit


def _signup(client, username):
    r = client.post(
        "/api/signup",
        json={"username": username, "email": f"{username}@x.com", "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r


def _get_user(username):
    from app.db import SessionLocal
    from app.models import User

    s = SessionLocal()
    try:
        return s.scalar(select(User).where(User.username == username))
    finally:
        s.close()


def test_upload_and_serve_avatar(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    _signup(client, "avuser")

    r = client.post(
        "/account/avatar",
        files={"avatar": ("a.png", PNG_1x1, "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/account"

    user = _get_user("avuser")
    assert user.avatar_path == f"avatars/{user.id}.png"
    # The file actually landed under the monkeypatched storage dir.
    assert (tmp_path / "avatars" / f"{user.id}.png").read_bytes() == PNG_1x1

    served = client.get("/avatar/avuser")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == PNG_1x1
    assert "max-age=300" in served.headers.get("cache-control", "")


def test_oversized_avatar_is_rejected(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    _signup(client, "bigpic")

    # Valid PNG header but > 2 MB payload.
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 64)
    r = client.post(
        "/account/avatar",
        files={"avatar": ("big.png", oversized, "image/png")},
        follow_redirects=False,
    )
    # Rejected: re-renders /account (200), not a redirect.
    assert r.status_code == 200
    assert _get_user("bigpic").avatar_path is None


def test_non_image_is_rejected(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    _signup(client, "notpic")

    r = client.post(
        "/account/avatar",
        files={"avatar": ("a.txt", b"hello", "text/plain")},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert _get_user("notpic").avatar_path is None


def test_mislabeled_image_bytes_rejected(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    _signup(client, "faker")

    # Declared as PNG but the bytes are not an image.
    r = client.post(
        "/account/avatar",
        files={"avatar": ("a.png", b"not really a png", "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert _get_user("faker").avatar_path is None


def test_avatar_missing_for_user_without_one_is_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    _signup(client, "plain")

    r = client.get("/avatar/plain")
    assert r.status_code == 404


def test_avatar_unknown_user_is_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.avatars.settings.storage_dir", str(tmp_path))
    r = client.get("/avatar/ghost")
    assert r.status_code == 404
