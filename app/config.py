import os

class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    s3_bucket = os.getenv("S3_BUCKET", "dothub-test")
    # ponytail: dev/test escape hatch. When set, bundles go to this local dir
    # instead of S3 (no AWS needed to run locally). Unset in prod for real S3.
    storage_dir = os.getenv("STORAGE_DIR")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    session_secret = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    max_bundle_bytes = int(os.getenv("MAX_BUNDLE_BYTES", str(5 * 1024 * 1024)))
    max_file_bytes = int(os.getenv("MAX_FILE_BYTES", str(1024 * 1024)))

settings = Settings()


def assert_prod_secret(s: Settings = settings) -> None:
    """Fail closed: a prod (https) deploy must not run on the dev fallback secret."""
    if s.base_url.startswith("https") and s.session_secret == "dev-secret-change-me":
        raise RuntimeError(
            "SESSION_SECRET must be set when base_url is https. "
            "Refusing to boot on the dev fallback secret."
        )
