import app.models  # noqa: register tables
from fastapi.testclient import TestClient

def test_static_css_served(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert "--blue:#2536c9" in r.text

def test_app_boots_with_web_router(client):
    # health still works and an unknown page is a clean 404, not a 500
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/nope").status_code == 404
