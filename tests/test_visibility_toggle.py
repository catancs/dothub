import app.models  # noqa: F401 - register tables before the db fixture's create_all
from app import setups  # noqa: F401


def _signup(client, name):
    r = client.post("/api/signup",
                    json={"username": name, "email": f"{name}@x.com", "password": "Testpass123"})
    assert r.status_code == 200


def _publish(client, title, is_public=None):
    body = {"title": title, "description": "d", "files": {"CLAUDE.md": "x"}}
    if is_public is not None:
        body["is_public"] = is_public
    return client.post("/api/setups", json=body).json()


def test_api_publish_is_public_by_default(client, s3):
    _signup(client, "apub")
    res = _publish(client, "Api Pub")
    assert res["is_public"] is True
    assert any(s["slug"] == "api-pub" for s in client.get("/api/setups").json())


def test_api_publish_can_be_private(client, s3):
    _signup(client, "apriv")
    res = _publish(client, "Api Priv", is_public=False)
    assert res["is_public"] is False
    assert not any(s["slug"] == "api-priv" for s in client.get("/api/setups").json())


def test_owner_can_toggle_visibility(client, s3):
    _signup(client, "vowner")
    slug = _publish(client, "Vis", is_public=False)["slug"]
    assert not any(s["slug"] == slug for s in client.get("/api/setups").json())

    r = client.post(f"/api/setups/{slug}/visibility", json={"is_public": True})
    assert r.status_code == 200 and r.json()["is_public"] is True
    assert any(s["slug"] == slug for s in client.get("/api/setups").json())

    r = client.post(f"/api/setups/{slug}/visibility", json={"is_public": False})
    assert r.status_code == 200 and r.json()["is_public"] is False
    assert not any(s["slug"] == slug for s in client.get("/api/setups").json())


def test_non_owner_cannot_toggle_visibility(client, s3):
    _signup(client, "vowner2")
    slug = _publish(client, "Vis2")["slug"]
    _signup(client, "vstranger")  # client session is now the stranger
    r = client.post(f"/api/setups/{slug}/visibility", json={"is_public": False})
    assert r.status_code == 403


def test_visibility_requires_auth(client, s3):
    _signup(client, "vauth")
    slug = _publish(client, "Vis3")["slug"]
    from app.main import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app()) as anon:
        r = anon.post(f"/api/setups/{slug}/visibility", json={"is_public": False})
        assert r.status_code == 401
