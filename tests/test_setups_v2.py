import app.models  # noqa: F401 - register tables on Base.metadata before db fixture's create_all

import pytest

from app import setups
from app.models import User, Setup, SetupVersion, PullEvent, Follow


def _mk_user(db, name="cata"):
    u = User(username=name, email=f"{name}@x.com", password_hash="h")
    db.add(u)
    db.commit()
    return u


FILES = {
    "CLAUDE.md": "be lazy",
    "hooks/hooks.json": '{"hooks": {"PreToolUse": [{"hooks": [{"type":"command","command":"echo hi"}]}]}}',
}

FILES_V2 = {
    "CLAUDE.md": "be lazy v2",
    "settings.json": '{"model": "opus"}',
}


def test_install_with_user_records_pull(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)
    s = db.query(Setup).filter_by(slug="my-flow").one()

    setups.install(db, "my-flow", user=u)

    assert db.query(Setup).filter_by(slug="my-flow").one().downloads == 1
    events = db.query(PullEvent).all()
    assert len(events) == 1
    ev = events[0]
    assert ev.user_id == u.id
    assert ev.setup_id == s.id
    assert ev.version == 1


def test_install_without_user_bumps_downloads_no_pull(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)

    setups.install(db, "my-flow")

    assert db.query(Setup).filter_by(slug="my-flow").one().downloads == 1
    assert db.query(PullEvent).count() == 0


def test_preview_include_files_returns_contents(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)

    full = setups.preview(db, "my-flow", include_files=True)
    assert full["file_contents"] == FILES
    assert full["files"] == sorted(FILES)

    lean = setups.preview(db, "my-flow")
    assert "file_contents" not in lean
    assert lean["files"] == sorted(FILES)


def test_revert_as_owner_appends_new_version(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)
    setups.publish(db, u, "My Flow", "desc v2", FILES_V2)

    s = db.query(Setup).filter_by(slug="my-flow").one()
    downloads_before = s.downloads
    v1 = db.query(SetupVersion).filter_by(setup_id=s.id, version=1).one()

    res = setups.revert(db, u, "my-flow", 1)

    assert res["version"] == 3
    assert res["reverted_from"] == 1
    s = db.query(Setup).filter_by(slug="my-flow").one()
    assert s.latest_version == 3
    assert s.downloads == downloads_before
    v3 = db.query(SetupVersion).filter_by(setup_id=s.id, version=3).one()
    assert v3.manifest_json == v1.manifest_json


def test_revert_by_non_owner_raises_ownership_error(db, s3):
    a = _mk_user(db, "alice")
    b = _mk_user(db, "bob")
    setups.publish(db, a, "Shared", "x", FILES)
    with pytest.raises(setups.OwnershipError):
        setups.revert(db, b, "shared", 1)


def test_revert_missing_version_raises_not_found(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)
    with pytest.raises(setups.NotFound):
        setups.revert(db, u, "my-flow", 99)


def test_trending_orders_by_recent_pulls(db, s3):
    u = _mk_user(db)
    setups.publish(db, u, "Alpha", "a", FILES, slug="alpha")
    setups.publish(db, u, "Beta", "b", FILES, slug="beta")

    setups.install(db, "beta", user=u)

    rows = setups.list_setups(db, window="7d")
    slugs = [r["slug"] for r in rows]
    assert slugs[0] == "beta"
    assert set(slugs) == {"alpha", "beta"}
    beta = next(r for r in rows if r["slug"] == "beta")
    assert beta["recent_pulls"] == 1


def test_following_lists_only_followees_setups(db, s3):
    a = _mk_user(db, "alice")
    b = _mk_user(db, "bob")
    setups.publish(db, a, "Alice Flow", "a", FILES, slug="alice-flow")
    setups.publish(db, b, "Bob Flow", "b", FILES, slug="bob-flow")

    db.add(Follow(follower_id=a.id, followee_id=b.id))
    db.commit()

    rows = setups.list_setups(db, following_of=a)
    slugs = [r["slug"] for r in rows]
    assert slugs == ["bob-flow"]
