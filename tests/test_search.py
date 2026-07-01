import pytest
from app import setups, bundle
from app.models import User


@pytest.fixture
def seeded(db):
    u = User(username="author", email="a@x.com", password_hash="h")
    db.add(u); db.flush()
    # no-code setup
    setups.publish(db, u, "Pure Skills", "desc",
                  {"skills/a/SKILL.md": "# a"}, slug="pure-skills")
    # hooks setup
    setups.publish(db, u, "Hooked", "desc",
                  {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'},
                  slug="hooked")
    return u


def test_filter_runs_code_false(db, s3, seeded):
    items = setups.list_setups(db, runs_code=False)
    slugs = {i["slug"] for i in items}
    assert "pure-skills" in slugs
    assert "hooked" not in slugs


def test_filter_runs_code_true(db, s3, seeded):
    items = setups.list_setups(db, runs_code=True)
    slugs = {i["slug"] for i in items}
    assert "hooked" in slugs
    assert "pure-skills" not in slugs


def test_filter_by_tag(db, s3, seeded):
    items = setups.list_setups(db, tag="hooks")
    assert any(i["slug"] == "hooked" for i in items)
    items = setups.list_setups(db, tag="skills-only")
    assert any(i["slug"] == "pure-skills" for i in items)


def test_query_filter(db, s3, seeded):
    items = setups.list_setups(db, query="Hook")
    assert any(i["slug"] == "hooked" for i in items)
    assert all(i["slug"] != "pure-skills" for i in items)


def test_list_returns_tags(db, s3, seeded):
    items = setups.list_setups(db, query="Hook")
    hooked = next(i for i in items if i["slug"] == "hooked")
    assert "hooks" in hooked["tags"]
