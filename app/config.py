import os

class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    s3_bucket = os.getenv("S3_BUCKET", "dothub-test")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    session_secret = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    max_bundle_bytes = int(os.getenv("MAX_BUNDLE_BYTES", str(5 * 1024 * 1024)))

settings = Settings()
