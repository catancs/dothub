from datetime import datetime

import app.models  # noqa: F401 — register ORM models with Base.metadata before schema creation


def test_user_and_setup_roundtrip(db):
    from app.models import User, Setup, SetupVersion
    u = User(username="cata", email="c@example.com", password_hash="x")
    db.add(u); db.commit()
    s = Setup(owner_id=u.id, slug="my-flow", title="My Flow", description="d", latest_version=1)
    db.add(s); db.commit()
    v = SetupVersion(setup_id=s.id, version=1, manifest_json={"runs_code": False},
                     archive_key="my-flow/v1.tar.gz", size_bytes=10)
    db.add(v); db.commit()
    assert s.downloads == 0
    assert isinstance(u.created_at, datetime)
    assert v.manifest_json["runs_code"] is False


def test_setup_version_unique_constraint(db):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models import User, Setup, SetupVersion
    u = User(username="u", email="u@x.com", password_hash="x"); db.add(u); db.commit()
    s = Setup(owner_id=u.id, slug="s", title="t", description="d", latest_version=1)
    db.add(s); db.commit()
    db.add(SetupVersion(setup_id=s.id, version=1, manifest_json={}, archive_key="k1", size_bytes=1))
    db.commit()
    db.add(SetupVersion(setup_id=s.id, version=1, manifest_json={}, archive_key="k2", size_bytes=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
