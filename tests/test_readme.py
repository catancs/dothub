def test_detail_shows_readme_when_present(client, s3):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "With Readme", "short desc",
                  {"skills/a/SKILL.md": "# a", "README.md": "# My Setup\n\nLong form text here."},
                  slug="with-readme")
    db.commit(); db.close()

    r = client.get("/s/with-readme")
    assert r.status_code == 200
    assert "Long form text here" in r.text
    assert "short desc" in r.text  # description still present


def test_detail_falls_back_to_description_without_readme(client, s3):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "No Readme", "the description", {"skills/a/SKILL.md": "# a"}, slug="no-readme")
    db.commit(); db.close()

    r = client.get("/s/no-readme")
    assert r.status_code == 200
    assert "the description" in r.text
