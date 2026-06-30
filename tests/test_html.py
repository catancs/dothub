def _publish(client, s3):
    client.post("/api/signup", json={"username": "cata", "email": "c@x.com", "password": "pw"})
    client.post("/api/setups", json={
        "title": "My Flow", "description": "neat",
        "files": {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"echo HOOKCMD"}]}]}}'}})

def test_feed_lists_setup(client, s3):
    _publish(client, s3)
    r = client.get("/")
    assert r.status_code == 200
    assert "My Flow" in r.text

def test_detail_shows_hook_command_and_notice(client, s3):
    _publish(client, s3)
    r = client.get("/s/my-flow")
    assert r.status_code == 200
    assert "echo HOOKCMD" in r.text          # exact command visible
    assert "responsibility" in r.text.lower()  # caveat-emptor notice
