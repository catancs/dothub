import app.models  # noqa: F401 — register tables on Base.metadata before db fixture's create_all
from app import setups  # noqa: F401 — same: ensure models import at collection time

import pytest


def _mk_user(db, name="cata"):
    from app.models import User
    u = User(username=name, email=f"{name}@x.com", password_hash="x")
    db.add(u); db.commit()
    return u

FILES = {
    "CLAUDE.md": "be lazy",
    "hooks/hooks.json": '{"hooks": {"PreToolUse": [{"hooks": [{"type":"command","command":"echo hi"}]}]}}',
}

def test_publish_then_preview_then_install(db, s3):
    from app import setups
    u = _mk_user(db)
    res = setups.publish(db, u, "My Flow", "desc", FILES)
    assert res["slug"] == "my-flow" and res["version"] == 1

    prev = setups.preview(db, "my-flow")
    assert prev["effects"]["runs_code"] is True
    assert "CLAUDE.md" in prev["files"]

    inst = setups.install(db, "my-flow")
    assert inst["files"] == FILES
    assert inst["effects"]["hooks"][0]["command"] == "echo hi"

def test_install_increments_downloads_preview_does_not(db, s3):
    from app import setups
    from app.models import Setup
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)
    setups.preview(db, "my-flow")
    setups.install(db, "my-flow")
    setups.install(db, "my-flow")
    assert db.query(Setup).filter_by(slug="my-flow").one().downloads == 2

def test_republish_bumps_version(db, s3):
    from app import setups
    u = _mk_user(db)
    setups.publish(db, u, "My Flow", "desc", FILES)
    res2 = setups.publish(db, u, "My Flow", "desc v2", {"CLAUDE.md": "v2"})
    assert res2["version"] == 2

def test_publish_to_others_slug_forbidden(db, s3):
    from app import setups
    a = _mk_user(db, "alice")
    b = _mk_user(db, "bob")
    setups.publish(db, a, "Shared", "x", FILES)  # slug "shared"
    with pytest.raises(setups.OwnershipError):
        setups.publish(db, b, "Shared", "y", FILES)

def test_publish_rejects_bad_bundle(db, s3):
    from app import setups
    from app.bundle import BundleError
    u = _mk_user(db)
    with pytest.raises(BundleError):
        setups.publish(db, u, "Bad", "x", {"../evil": "x"})
