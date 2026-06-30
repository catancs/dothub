from app.bundle import effects_manifest
import json

def test_plugins_parsed_and_runs_code():
    files = {"plugins.json": json.dumps({
        "plugins": [{"name": "superpowers", "marketplace": "official", "enabled": True}],
        "marketplaces": {"official": {"source": "github", "repo": "anthropics/claude-plugins"}},
    })}
    m = effects_manifest(files)
    assert m["plugins"] == [{"name": "superpowers", "marketplace": "official", "source": "anthropics/claude-plugins"}]
    assert m["counts"]["plugins"] == 1
    assert m["runs_code"] is True

def test_malformed_plugins_tolerated():
    m = effects_manifest({"plugins.json": "{not json"})
    assert m["plugins"] == [] and m["counts"]["plugins"] == 0
