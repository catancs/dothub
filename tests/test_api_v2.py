"""v2 API surface: auth-gated download, revert, follow, account, MCP install auth.

Mirrors tests/test_api.py's TestClient + signup/mint-key approach. The TestClient
keeps the session cookie set by /api/signup, so authed calls work without headers.
"""

import pytest


def _signup(client, username, email="", password="Testpass123"):
    email = email or f"{username}@x.com"
    r = client.post("/api/signup", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200
    return r


def _publish(client, title, files=None, headers=None):
    files = files or {"CLAUDE.md": "x"}
    r = client.post("/api/setups", json={"title": title, "description": "d", "files": files}, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_anonymous_download_returns_401(client, s3):
    # owner publishes a real setup
    _signup(client, "owner")
    _publish(client, "Real Flow")

    # a fresh client with no session cookie cannot download
    from app.main import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app()) as anon:
        r = anon.post("/api/setups/real-flow/download")
        assert r.status_code == 401


def test_authenticated_download_records_pull(client, s3, db):
    from app.models import Setup, PullEvent
    from sqlalchemy import select, func

    _signup(client, "puller")
    _publish(client, "Pull Flow")

    r = client.post("/api/setups/pull-flow/download")
    assert r.status_code == 200
    body = r.json()
    assert "files" in body
    assert body["version"] == 1

    # the download incremented downloads and recorded a PullEvent
    s = db.scalar(select(Setup).where(Setup.slug == "pull-flow"))
    assert s.downloads == 1
    pulls = db.scalar(select(func.count()).select_from(PullEvent).where(PullEvent.setup_id == s.id))
    assert pulls == 1


def test_revert_owner_other_user_and_missing_version(client, s3):
    # owner publishes v1 then v2 (same slug)
    _signup(client, "rev")
    _publish(client, "Rev Flow", files={"CLAUDE.md": "v1"})
    _publish(client, "Rev Flow", files={"CLAUDE.md": "v2"})

    # owner reverts to v1 -> creates v3
    r = client.post("/api/setups/rev-flow/revert", json={"version": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 3
    assert body["reverted_from"] == 1

    # missing version -> 404
    r = client.post("/api/setups/rev-flow/revert", json={"version": 99})
    assert r.status_code == 404

    # a different signed-in user cannot revert -> 403
    _signup(client, "intruder")
    r = client.post("/api/setups/rev-flow/revert", json={"version": 1})
    assert r.status_code == 403


def test_follow_then_unfollow_updates_state(client, s3, db):
    from app.models import User, Follow
    from sqlalchemy import select

    # create the followee account, then switch to the follower account
    _signup(client, "star")
    _signup(client, "fan")

    # follow returns following True
    r = client.post("/api/follow/star")
    assert r.status_code == 200
    assert r.json()["following"] is True

    # a second follow is idempotent (still True, one row only)
    r = client.post("/api/follow/star")
    assert r.status_code == 200
    assert r.json()["following"] is True
    fan = db.scalar(select(User).where(User.username == "fan"))
    star = db.scalar(select(User).where(User.username == "star"))
    rows = db.scalars(select(Follow).where(Follow.follower_id == fan.id, Follow.followee_id == star.id)).all()
    assert len(rows) == 1

    # self-follow -> 400
    r = client.post("/api/follow/fan")
    assert r.status_code == 400

    # unknown username -> 404
    r = client.post("/api/follow/nobody")
    assert r.status_code == 404

    # unfollow returns following False and removes the row
    r = client.delete("/api/follow/star")
    assert r.status_code == 200
    assert r.json()["following"] is False
    rows = db.scalars(select(Follow).where(Follow.follower_id == fan.id, Follow.followee_id == star.id)).all()
    assert len(rows) == 0


def test_account_update_persists(client, s3, db):
    from app.models import User
    from sqlalchemy import select

    _signup(client, "profile")
    r = client.post("/api/account", json={
        "display_name": "Pro File",
        "bio": "I build setups",
        "link_github": "https://github.com/profile",
        "link_linkedin": "https://linkedin.com/in/profile",
        "link_x": "https://x.com/profile",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True

    db.expire_all()
    u = db.scalar(select(User).where(User.username == "profile"))
    assert u.display_name == "Pro File"
    assert u.bio == "I build setups"
    assert u.link_github == "https://github.com/profile"
    assert u.link_linkedin == "https://linkedin.com/in/profile"
    assert u.link_x == "https://x.com/profile"


def test_mcp_install_requires_key(db, s3, monkeypatch):
    from app import mcp_server

    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: None)
    with pytest.raises(PermissionError):
        mcp_server.install_setup("any-slug")
