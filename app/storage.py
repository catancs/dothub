from pathlib import Path

import boto3

from .config import settings


def _client():
    return boto3.client("s3", region_name=settings.aws_region)


def _local_path(key: str) -> Path:
    return Path(settings.storage_dir) / key


def _encrypt(data: bytes) -> bytes:
    """Encrypt bundle bytes at rest when STORAGE_ENCRYPTION_KEY is set.

    Symmetric (Fernet), key held by the server. Protects the stored setup files
    against disk theft and leaked DB/backup dumps. With the key unset (dev/test)
    data is stored as-is so no crypto is needed to run locally.
    """
    if not settings.storage_encryption_key:
        return data
    from cryptography.fernet import Fernet

    return Fernet(settings.storage_encryption_key.encode()).encrypt(data)


def _decrypt(data: bytes) -> bytes:
    if not settings.storage_encryption_key:
        return data
    from cryptography.fernet import Fernet

    return Fernet(settings.storage_encryption_key.encode()).decrypt(data)


def put_archive(key: str, data: bytes) -> None:
    data = _encrypt(data)
    if settings.storage_dir:  # ponytail: local-disk backend
        p = _local_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)


def get_archive(key: str) -> bytes:
    if settings.storage_dir:
        raw = _local_path(key).read_bytes()
    else:
        raw = _client().get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    return _decrypt(raw)
