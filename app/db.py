from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings

class Base(DeclarativeBase):
    pass

if settings.database_url.startswith("sqlite"):
    # in-memory needs one shared connection across threads for tests
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(engine)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
