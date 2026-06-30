import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("S3_BUCKET", "dothub-test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def db():
    from app.db import Base, engine, SessionLocal
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
def s3():
    import boto3
    from moto import mock_aws
    from app.config import settings
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(Bucket=settings.s3_bucket)
        yield

@pytest.fixture
def client():
    from app.db import Base, engine
    Base.metadata.create_all(engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)
