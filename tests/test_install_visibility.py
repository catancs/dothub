import app.models  # noqa: F401 - register tables on Base.metadata before db fixture's create_all

import pytest
from sqlalchemy import select

from app import setups, security
from app.models import User, Setup


def _make_private(db):
    u = User(username="iowner", email="io@x.com", password_hash=security.hash_password("pw12345"))
    db.add(u); db.flush()
    setups.publish(db, u, "Private", "d", {"skills/a/SKILL.md": "# a"}, slug="ipriv")
    s = db.scalar(select(Setup).where(Setup.slug == "ipriv"))
    s.is_public = False
    db.commit()
    return u


def _stranger(db, name="istranger"):
    u = User(username=name, email=f"{name}@x.com", password_hash=security.hash_password("pw12345"))
    db.add(u); db.flush()
    return u


def test_install_rejects_non_public_for_non_owner(db, s3):
    _make_private(db)
    stranger = _stranger(db)
    with pytest.raises(setups.NotFound):
        setups.install(db, "ipriv", user=stranger)


def test_install_rejects_non_public_for_anonymous(db, s3):
    _make_private(db)
    with pytest.raises(setups.NotFound):
        setups.install(db, "ipriv", user=None)


def test_install_allows_owner_of_non_public(db, s3):
    u = _make_private(db)
    out = setups.install(db, "ipriv", user=u)
    assert out["slug"] == "ipriv"
    assert "skills/a/SKILL.md" in out["files"]


def test_install_allows_public_to_anyone(db, s3):
    _make_private(db)
    s = db.scalar(select(Setup).where(Setup.slug == "ipriv"))
    s.is_public = True
    db.commit()
    stranger = _stranger(db, name="istranger2")
    out = setups.install(db, "ipriv", user=stranger)
    assert out["slug"] == "ipriv"
    assert "skills/a/SKILL.md" in out["files"]


def test_download_non_public_non_owner_returns_404(client, s3):
    # owner signs up, publishes, then makes the setup private
    client.post("/api/signup", json={"username": "downo", "email": "downo@x.com", "password": "pw123456"})
    key = client.post("/api/keys", json={"label": "cli"}).json()["api_key"]
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"title": "Secret", "description": "d", "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
    slug = r.json()["slug"]

    # flip to private directly in the DB
    from app.db import SessionLocal
    from app.models import Setup
    dbs = SessionLocal()
    s = dbs.scalar(select(Setup).where(Setup.slug == slug))
    s.is_public = False
    dbs.commit(); dbs.close()

    # a different logged-in user cannot download it
    client.post("/api/signup", json={"username": "peeker", "email": "peeker@x.com", "password": "pw123456"})
    r = client.post(f"/api/setups/{slug}/download")
    assert r.status_code == 404


def test_download_non_public_owner_returns_200(client, s3):
    client.post("/api/signup", json={"username": "owno", "email": "owno@x.com", "password": "pw123456"})
    key = client.post("/api/keys", json={"label": "cli"}).json()["api_key"]
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"title": "Owner Secret", "description": "d", "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
    slug = r.json()["slug"]

    from app.db import SessionLocal
    from app.models import Setup
    dbs = SessionLocal()
    s = dbs.scalar(select(Setup).where(Setup.slug == slug))
    s.is_public = False
    dbs.commit(); dbs.close()

    # the same session (owner) can still download their own private setup
    r = client.post(f"/api/setups/{slug}/download")
    assert r.status_code == 200
    assert "files" in r.json()


def test_download_public_allows_any_logged_in_user(client, s3):
    client.post("/api/signup", json={"username": "pubo", "email": "pubo@x.com", "password": "pw123456"})
    r = client.post("/api/setups", json={"title": "Public Flow", "description": "d",
                                         "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
    slug = r.json()["slug"]

    # a second, unrelated user can download the public setup
    client.post("/api/signup", json={"username": "grabber", "email": "grabber@x.com", "password": "pw123456"})
    r = client.post(f"/api/setups/{slug}/download")
    assert r.status_code == 200
    assert "files" in r.json()
