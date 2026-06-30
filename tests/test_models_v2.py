import app.models  # noqa
import pytest
from sqlalchemy.exc import IntegrityError


def test_follow_unique(db):
    from app.models import User, Follow
    a = User(username="a", email="a@x", password_hash="h")
    b = User(username="b", email="b@x", password_hash="h")
    db.add_all([a, b]); db.commit()
    db.add(Follow(follower_id=a.id, followee_id=b.id)); db.commit()
    db.add(Follow(follower_id=a.id, followee_id=b.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_pull_event_and_profile_fields(db):
    from app.models import User, Setup, PullEvent
    u = User(username="p", email="p@x", password_hash="h", display_name="P", link_x="x.com/p")
    db.add(u); db.commit()
    s = Setup(owner_id=u.id, slug="s", title="S"); db.add(s); db.commit()
    db.add(PullEvent(user_id=u.id, setup_id=s.id, version=1)); db.commit()
    assert db.query(PullEvent).count() == 1
    assert u.display_name == "P" and u.link_x == "x.com/p"
