import boto3
from .config import settings

def _client():
    return boto3.client("s3", region_name=settings.aws_region)

def put_archive(key: str, data: bytes) -> None:
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)

def get_archive(key: str) -> bytes:
    obj = _client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()

def presign_get(key: str, expires: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
