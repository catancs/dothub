import app.models  # noqa: F401 - register tables on Base.metadata before db fixture's create_all

import pytest
from sqlalchemy import select

from app import setups, security
from app.models import User, Setup


def _make_private(db):
    u = User(username="owner", email="o@x.com", password_hash=security.hash_password("pw12345"))
    db.add(u); db.flush()
    setups.publish(db, u, "Private", "d", {"skills/a/SKILL.md": "# a"}, slug="priv")
    s = db.scalar(select(Setup).where(Setup.slug == "priv"))
    s.is_public = False
    db.commit()
    return u


def test_preview_rejects_non_public_for_non_owner(db, s3):
    u = _make_private(db)
    stranger = User(username="stranger", email="s@x.com", password_hash=security.hash_password("pw12345"))
    db.add(stranger); db.flush()
    with pytest.raises(setups.NotFound):
        setups.preview(db, "priv", viewer=stranger)


def test_preview_allows_owner_of_non_public(db, s3):
    u = _make_private(db)
    out = setups.preview(db, "priv", viewer=u)
    assert out["slug"] == "priv"


def test_preview_allows_public_to_anyone(db, s3):
    u = _make_private(db)
    s = db.scalar(select(Setup).where(Setup.slug == "priv"))
    s.is_public = True
    db.commit()
    stranger = User(username="stranger2", email="s2@x.com", password_hash=security.hash_password("pw12345"))
    db.add(stranger); db.flush()
    out = setups.preview(db, "priv", viewer=stranger)
    assert out["slug"] == "priv"
