import os

class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    s3_bucket = os.getenv("S3_BUCKET", "dothub-test")
    # ponytail: dev/test escape hatch — when set, bundles go to this local dir
    # instead of S3 (no AWS needed to run locally). Unset in prod → real S3.
    storage_dir = os.getenv("STORAGE_DIR")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    session_secret = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    max_bundle_bytes = int(os.getenv("MAX_BUNDLE_BYTES", str(5 * 1024 * 1024)))
    max_file_bytes = int(os.getenv("MAX_FILE_BYTES", str(1024 * 1024)))

settings = Settings()
