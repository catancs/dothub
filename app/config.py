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
    # email verification (AWS SES). ses_sender falsy -> dev/test mode: no SES call.
    ses_sender = os.getenv("SES_SENDER")
    ses_region = os.getenv("SES_REGION", os.getenv("AWS_REGION", "eu-north-1"))
    email_from = os.getenv("EMAIL_FROM", "no-reply@dothub.nl")
    require_email_verification = os.getenv("REQUIRE_EMAIL_VERIFICATION", "").lower() in {"1", "true", "yes"}
    # When set, the site admin gets an email each time a new user signs up.
    admin_notify_email = os.getenv("ADMIN_NOTIFY_EMAIL")
    # When set (a Fernet key), setup bundles are encrypted at rest on disk/S3.
    storage_encryption_key = os.getenv("STORAGE_ENCRYPTION_KEY")

settings = Settings()


def assert_prod_secret(s: Settings = settings) -> None:
    """Fail closed: a prod (https) deploy must not run on the dev fallback secret."""
    if s.base_url.startswith("https") and s.session_secret == "dev-secret-change-me":
        raise RuntimeError(
            "SESSION_SECRET must be set when base_url is https. "
            "Refusing to boot on the dev fallback secret."
        )
