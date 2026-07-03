"""Agent provenance: the publishing agent's declared `agent` slug is stored on
the setup and surfaced in preview/feed, defaulting to claude-code when omitted,
and surviving version bumps."""
import app.models  # noqa: F401 — register tables
from sqlalchemy import select

from app import setups
from app.models import User, Setup


def _user(db):
    u = User(username="cata", email="c@x.com", password_hash="x")
    db.add(u)
    db.commit()
    return u


def _setup(db, slug):
    return db.scalar(select(Setup).where(Setup.slug == slug))


def test_publish_defaults_to_claude_code(db, s3):
    u = _user(db)
    setups.publish(db, u, "T", "d", {"CLAUDE.md": "x"})
    assert _setup(db, "t").agent == "claude-code"


def test_publish_persists_declared_agent(db, s3):
    u = _user(db)
    setups.publish(db, u, "T", "d", {"CLAUDE.md": "x"}, agent="codex")
    assert _setup(db, "t").agent == "codex"
    assert setups.preview(db, "t")["agent"] == "codex"


def test_republish_updates_agent(db, s3):
    u = _user(db)
    setups.publish(db, u, "T", "d", {"CLAUDE.md": "x"}, agent="codex")
    setups.publish(db, u, "T", "d2", {"CLAUDE.md": "y"}, agent="cursor")
    s = _setup(db, "t")
    assert s.agent == "cursor"
    assert s.latest_version == 2


def test_feed_includes_agent(db, s3):
    u = _user(db)
    setups.publish(db, u, "Alpha", "d", {"CLAUDE.md": "x"}, agent="windsurf")
    items = setups.list_setups(db)
    assert any(i["agent"] == "windsurf" for i in items)


def test_unknown_agent_accepted(db, s3):
    # open-ended: any string is stored, no validation against the known list
    u = _user(db)
    setups.publish(db, u, "T", "d", {"CLAUDE.md": "x"}, agent="some-future-agent")
    assert _setup(db, "t").agent == "some-future-agent"
