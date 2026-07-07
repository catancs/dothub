"""Profile-picture (avatar) storage + validation.

Avatars live on local disk under ``settings.storage_dir`` at
``avatars/{user_id}.{ext}`` — the same local-disk root used by bundles.
``settings.storage_dir`` is read LAZILY inside each function so tests can
monkeypatch ``app.avatars.settings.storage_dir`` before calling in.
"""

import os

from .config import settings

MAX_AVATAR_BYTES = 2 * 1024 * 1024

# Allowed upload content-type -> stored file extension.
ALLOWED = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}

# Stored extension -> content-type served back on read.
_EXT_CONTENT_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

_ALL_EXTS = ("png", "jpg", "webp", "gif")


def _header_is_image(content_type: str, data: bytes) -> bool:
    """Sniff the magic bytes so a mislabelled/non-image upload is rejected."""
    if content_type == "image/png":
        return data[:4] == b"\x89PNG"
    if content_type == "image/jpeg":
        return data[:2] == b"\xff\xd8"
    if content_type == "image/gif":
        return data[:4] == b"GIF8"
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def save_avatar(user_id: int, content_type: str, data: bytes) -> str:
    """Validate and store an avatar; return its storage key.

    Raises ValueError if the content-type is unsupported, the payload is too
    large, or the byte header does not look like the declared image type.
    """
    ext = ALLOWED.get(content_type)
    if ext is None:
        raise ValueError(
            "unsupported image type; use PNG, JPEG, WebP or GIF"
        )
    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError("image too large; the maximum size is 2 MB")
    if not _header_is_image(content_type, data):
        raise ValueError("file content does not look like a valid image")

    base = os.path.join(settings.storage_dir, "avatars")
    os.makedirs(base, exist_ok=True)

    # Best-effort: drop any prior avatar for this user stored under a different
    # extension, so the new one is the only file that answers /avatar/{user}.
    for other in _ALL_EXTS:
        if other == ext:
            continue
        try:
            os.remove(os.path.join(base, f"{user_id}.{other}"))
        except OSError:
            pass

    path = os.path.join(base, f"{user_id}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return f"avatars/{user_id}.{ext}"


def read_avatar(key: str) -> tuple[bytes, str]:
    """Read an avatar by storage key; return (bytes, content_type).

    Raises FileNotFoundError if the file is missing on disk.
    """
    path = os.path.join(settings.storage_dir, key)
    ext = os.path.splitext(key)[1].lstrip(".").lower()
    content_type = _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")
    with open(path, "rb") as f:
        return f.read(), content_type
