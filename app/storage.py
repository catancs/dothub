from pathlib import Path

import boto3

from .config import settings


def _client():
    return boto3.client("s3", region_name=settings.aws_region)


def _local_path(key: str) -> Path:
    return Path(settings.storage_dir) / key


def put_archive(key: str, data: bytes) -> None:
    if settings.storage_dir:  # ponytail: local-disk backend for dev/test
        p = _local_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)


def get_archive(key: str) -> bytes:
    if settings.storage_dir:
        return _local_path(key).read_bytes()
    obj = _client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()
