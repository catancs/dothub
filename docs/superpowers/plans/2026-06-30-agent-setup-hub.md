# Agent Setup Hub (dothub) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hosted service that lets users publish their whole Claude Code setup as a versioned bundle, browse a public feed, and pull setups in — with the agent doing it itself via a remote MCP server, and a transparency-first install preview.

**Architecture:** A single FastAPI app is both a JSON/HTML web service and a remote MCP server. Pure-logic modules (bundle validation, effects manifest) and I/O wrappers (S3 storage, auth) are composed by a core `setups.py` that both the REST routes and the MCP tools call. Bundle bytes live in S3; metadata lives in Postgres.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (sync), psycopg3 (Postgres) / SQLite (tests), boto3 + moto, FastMCP, Jinja2, bcrypt, pytest.

## Global Constraints

- **Python:** 3.11+
- **DB types:** use SQLAlchemy portable `JSON` (not Postgres-only `JSONB`) so tests run on SQLite.
- **Bundle limits (enforced on publish):** ≤ `MAX_BUNDLE_BYTES` (default 5 MB) · ≤ 500 files · UTF-8 text only · reject any path that is absolute, contains `..`, or escapes root.
- **Auth split:** humans use email+password (bcrypt) → signed session cookie. Agents/programmatic use an API key (`dh_…`, stored as SHA-256 hash) via `Authorization: Bearer …`.
- **Slug:** globally unique. Publish to a slug you don't own → `403`.
- **Effects manifest** is computed at publish and stored in `setup_version.manifest_json`; it MUST contain `hooks` (exact commands), `mcp_servers`, `counts`, `runs_code`.
- **Trust model:** server makes effects maximally visible; it does NOT sandbox or verify. Install requires the agent to show effects + diff before writing (client-side responsibility).
- **Deployment target:** AWS cloud-native only (EC2 + RDS + S3 + Nginx + certbot).
- **Project root:** `dothub/`. All paths below are relative to it. Run `pytest` and `git` from `dothub/`.
- **Commits:** conventional commits, one per task minimum.

---

### Task 1: Project skeleton, config, DB engine, health check

**Files:**
- Create: `dothub/requirements.txt`
- Create: `dothub/app/__init__.py` (empty)
- Create: `dothub/app/config.py`
- Create: `dothub/app/db.py`
- Create: `dothub/app/main.py`
- Create: `dothub/tests/__init__.py` (empty)
- Create: `dothub/tests/conftest.py`
- Test: `dothub/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings` (attrs: `database_url`, `s3_bucket`, `aws_region`, `base_url`, `session_secret`, `max_bundle_bytes`). `app.db.Base`, `app.db.engine`, `app.db.SessionLocal`, `app.db.get_session()`, `app.db.init_db()`. `app.main.create_app()`.

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
gunicorn==23.*
sqlalchemy==2.0.*
psycopg[binary]==3.2.*
jinja2==3.1.*
python-multipart==0.0.*
bcrypt==4.2.*
boto3==1.35.*
fastmcp==2.3.*
itsdangerous==2.2.*
pytest==8.*
httpx==0.27.*
moto[s3]==5.*
```

- [ ] **Step 2: Write the failing test**

`dothub/tests/test_health.py`:
```python
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Run it, expect failure**

Run: `cd dothub && pytest tests/test_health.py -v`
Expected: error/fail — `client` fixture or app not defined yet.

- [ ] **Step 4: Write `config.py`**

```python
import os

class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    s3_bucket = os.getenv("S3_BUCKET", "dothub-test")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    session_secret = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    max_bundle_bytes = int(os.getenv("MAX_BUNDLE_BYTES", str(5 * 1024 * 1024)))

settings = Settings()
```

- [ ] **Step 5: Write `db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings

class Base(DeclarativeBase):
    pass

if settings.database_url.startswith("sqlite"):
    # in-memory needs one shared connection across threads for tests
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(engine)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Write `main.py`**

```python
from fastapi import FastAPI
from .db import init_db

def create_app() -> FastAPI:
    app = FastAPI(title="dothub")

    @app.on_event("startup")
    def _startup():
        init_db()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

app = create_app()
```

- [ ] **Step 7: Write `conftest.py`**

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("S3_BUCKET", "dothub-test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def db():
    from app.db import Base, engine, SessionLocal
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
def s3():
    import boto3
    from moto import mock_aws
    from app.config import settings
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(Bucket=settings.s3_bucket)
        yield

@pytest.fixture
def client():
    from app.db import Base, engine
    Base.metadata.create_all(engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 8: Run the test, expect pass**

Run: `cd dothub && pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add dothub/requirements.txt dothub/app dothub/tests
git commit -m "feat: project skeleton, config, db engine, health check"
```

---

### Task 2: Data models

**Files:**
- Create: `dothub/app/models.py`
- Test: `dothub/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base`.
- Produces: ORM classes `User(id, username, email, password_hash, created_at)`, `ApiKey(id, user_id, key_hash, label, created_at, last_used_at)`, `Setup(id, owner_id, slug, title, description, latest_version, downloads, is_public, created_at, updated_at)`, `SetupVersion(id, setup_id, version, manifest_json, archive_key, size_bytes, created_at)`.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_models.py`:
```python
from datetime import datetime

def test_user_and_setup_roundtrip(db):
    from app.models import User, Setup, SetupVersion
    u = User(username="cata", email="c@example.com", password_hash="x")
    db.add(u); db.commit()
    s = Setup(owner_id=u.id, slug="my-flow", title="My Flow", description="d", latest_version=1)
    db.add(s); db.commit()
    v = SetupVersion(setup_id=s.id, version=1, manifest_json={"runs_code": False},
                     archive_key="my-flow/v1.tar.gz", size_bytes=10)
    db.add(v); db.commit()
    assert s.downloads == 0
    assert isinstance(u.created_at, datetime)
    assert v.manifest_json["runs_code"] is False
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_models.py -v`
Expected: FAIL — `app.models` missing.

- [ ] **Step 3: Write `models.py`**

```python
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ApiKey(Base):
    __tablename__ = "api_key"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Setup(Base):
    __tablename__ = "setup"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(2000), default="")
    latest_version: Mapped[int] = mapped_column(Integer, default=1)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SetupVersion(Base):
    __tablename__ = "setup_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(ForeignKey("setup.id"))
    version: Mapped[int] = mapped_column(Integer)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    archive_key: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Run the test, expect pass**

Run: `cd dothub && pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dothub/app/models.py dothub/tests/test_models.py
git commit -m "feat: data models (user, api_key, setup, setup_version)"
```

---

### Task 3: Bundle module — validation, pack/unpack, effects manifest

**Files:**
- Create: `dothub/app/bundle.py`
- Test: `dothub/tests/test_bundle.py`

**Interfaces:**
- Produces: `BundleError(ValueError)`; `validate_files(files: dict[str,str], max_bytes: int, max_files: int = 500) -> None`; `pack(files: dict[str,str]) -> bytes`; `unpack(data: bytes) -> dict[str,str]`; `effects_manifest(files: dict[str,str]) -> dict` returning keys `hooks` (list of `{event, command}`), `mcp_servers` (list of `{name, command, args}`), `counts` (`{skills, commands, agents, rules}`), `runs_code` (bool), `secret_flags` (list[str]); `slugify(text: str) -> str`.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_bundle.py`:
```python
import pytest
from app.bundle import validate_files, pack, unpack, effects_manifest, slugify, BundleError

def test_validate_rejects_traversal():
    with pytest.raises(BundleError):
        validate_files({"../evil.sh": "x"}, max_bytes=1000)

def test_validate_rejects_absolute():
    with pytest.raises(BundleError):
        validate_files({"/etc/passwd": "x"}, max_bytes=1000)

def test_validate_rejects_oversize():
    with pytest.raises(BundleError):
        validate_files({"a.md": "x" * 2000}, max_bytes=1000)

def test_pack_unpack_roundtrip():
    files = {"CLAUDE.md": "hello", "skills/x/SKILL.md": "do x"}
    assert unpack(pack(files)) == files

def test_pack_is_deterministic():
    files = {"b.md": "1", "a.md": "2"}
    assert pack(files) == pack(files)

def test_effects_manifest_detects_hooks_and_mcp():
    files = {
        "hooks/hooks.json": '{"hooks": {"PreToolUse": [{"hooks": [{"type":"command","command":"rm -rf /tmp/x"}]}]}}',
        ".mcp.json": '{"mcpServers": {"weather": {"command": "uvx", "args": ["weather-mcp"]}}}',
        "skills/a/SKILL.md": "x",
        "commands/c.md": "x",
    }
    m = effects_manifest(files)
    assert m["runs_code"] is True
    assert {"event": "PreToolUse", "command": "rm -rf /tmp/x"} in m["hooks"]
    assert {"name": "weather", "command": "uvx", "args": ["weather-mcp"]} in m["mcp_servers"]
    assert m["counts"]["skills"] == 1 and m["counts"]["commands"] == 1

def test_effects_manifest_no_code():
    m = effects_manifest({"CLAUDE.md": "just rules"})
    assert m["runs_code"] is False

def test_secret_flag():
    m = effects_manifest({"x.md": "key sk-ABC123 here"})
    assert any("x.md" in f for f in m["secret_flags"])

def test_slugify():
    assert slugify("My Cool Flow!") == "my-cool-flow"
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_bundle.py -v`
Expected: FAIL — `app.bundle` missing.

- [ ] **Step 3: Write `bundle.py`**

```python
import io
import json
import re
import tarfile
from posixpath import normpath

class BundleError(ValueError):
    pass

SECRET_PATTERNS = [r"sk-[A-Za-z0-9]{8,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]

def validate_files(files: dict[str, str], max_bytes: int, max_files: int = 500) -> None:
    if not files:
        raise BundleError("empty bundle")
    if len(files) > max_files:
        raise BundleError(f"too many files (>{max_files})")
    total = 0
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise BundleError("paths and contents must be strings")
        if path.startswith("/") or path.startswith("\\"):
            raise BundleError(f"absolute path not allowed: {path}")
        norm = normpath(path)
        if norm.startswith("..") or norm.startswith("/") or ".." in norm.split("/"):
            raise BundleError(f"path escapes bundle root: {path}")
        total += len(content.encode("utf-8"))
    if total > max_bytes:
        raise BundleError(f"bundle too large ({total} > {max_bytes} bytes)")

def pack(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    # mtime=0 + sorted entries → deterministic bytes
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tar:
        for path in sorted(files):
            data = files[path].encode("utf-8")
            info = tarfile.TarInfo(name=path)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()

def unpack(data: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for info in tar.getmembers():
            if not info.isfile():
                continue
            out[info.name] = tar.extractfile(info).read().decode("utf-8")
    return out

def _walk_commands(node):
    """Collect every {'command': ...} string found anywhere in a hooks.json tree."""
    found = []
    if isinstance(node, dict):
        if isinstance(node.get("command"), str):
            found.append(node["command"])
        for v in node.values():
            found += _walk_commands(v)
    elif isinstance(node, list):
        for v in node:
            found += _walk_commands(v)
    return found

def effects_manifest(files: dict[str, str]) -> dict:
    hooks = []
    if "hooks/hooks.json" in files:
        try:
            tree = json.loads(files["hooks/hooks.json"]).get("hooks", {})
            for event, entries in tree.items():
                for cmd in _walk_commands(entries):
                    hooks.append({"event": event, "command": cmd})
        except (ValueError, AttributeError):
            pass

    mcp_servers = []
    if ".mcp.json" in files:
        try:
            servers = json.loads(files[".mcp.json"]).get("mcpServers", {})
            for name, cfg in servers.items():
                mcp_servers.append({
                    "name": name,
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                })
        except (ValueError, AttributeError):
            pass

    counts = {
        "skills": sum(1 for p in files if p.startswith("skills/") and p.endswith("SKILL.md")),
        "commands": sum(1 for p in files if p.startswith("commands/")),
        "agents": sum(1 for p in files if p.startswith("agents/")),
        "rules": sum(1 for p in files if p == "CLAUDE.md" or p.startswith(".claude/rules/")),
    }

    secret_flags = []
    for path, content in files.items():
        for pat in SECRET_PATTERNS:
            if re.search(pat, content):
                secret_flags.append(f"{path}: matched {pat}")
                break

    return {
        "hooks": hooks,
        "mcp_servers": mcp_servers,
        "counts": counts,
        "runs_code": bool(hooks or mcp_servers),
        "secret_flags": secret_flags,
    }

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "setup"
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_bundle.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add dothub/app/bundle.py dothub/tests/test_bundle.py
git commit -m "feat: bundle validation, deterministic pack/unpack, effects manifest"
```

---

### Task 4: Storage module (S3 via boto3)

**Files:**
- Create: `dothub/app/storage.py`
- Test: `dothub/tests/test_storage.py`

**Interfaces:**
- Consumes: `app.config.settings`.
- Produces: `put_archive(key: str, data: bytes) -> None`; `get_archive(key: str) -> bytes`; `presign_get(key: str, expires: int = 3600) -> str`.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_storage.py`:
```python
def test_put_get_roundtrip(s3):
    from app.storage import put_archive, get_archive
    put_archive("a/v1.tar.gz", b"hello-bytes")
    assert get_archive("a/v1.tar.gz") == b"hello-bytes"

def test_presign_returns_url(s3):
    from app.storage import put_archive, presign_get
    put_archive("a/v1.tar.gz", b"x")
    url = presign_get("a/v1.tar.gz")
    assert url.startswith("http") and "a/v1.tar.gz" in url
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_storage.py -v`
Expected: FAIL — `app.storage` missing.

- [ ] **Step 3: Write `storage.py`**

```python
import boto3
from .config import settings

def _client():
    return boto3.client("s3", region_name=settings.aws_region)

def put_archive(key: str, data: bytes) -> None:
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)

def get_archive(key: str) -> bytes:
    obj = _client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()

def presign_get(key: str, expires: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_storage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dothub/app/storage.py dothub/tests/test_storage.py
git commit -m "feat: S3 storage wrapper (put/get/presign)"
```

---

### Task 5: Security module (passwords + API keys)

**Files:**
- Create: `dothub/app/security.py`
- Test: `dothub/tests/test_security.py`

**Interfaces:**
- Produces: `hash_password(pw: str) -> str`; `verify_password(pw: str, hashed: str) -> bool`; `generate_api_key() -> tuple[str, str]` returning `(plain, key_hash)`; `hash_api_key(plain: str) -> str`.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_security.py`:
```python
def test_password_hash_verify():
    from app.security import hash_password, verify_password
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False

def test_api_key_generation_and_hash():
    from app.security import generate_api_key, hash_api_key
    plain, key_hash = generate_api_key()
    assert plain.startswith("dh_")
    assert hash_api_key(plain) == key_hash
    assert hash_api_key("dh_other") != key_hash
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_security.py -v`
Expected: FAIL — `app.security` missing.

- [ ] **Step 3: Write `security.py`**

```python
import hashlib
import secrets
import bcrypt

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False

def hash_api_key(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()

def generate_api_key() -> tuple[str, str]:
    plain = "dh_" + secrets.token_urlsafe(32)
    return plain, hash_api_key(plain)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dothub/app/security.py dothub/tests/test_security.py
git commit -m "feat: password hashing and API key generation"
```

---

### Task 6: Core setups logic (publish / preview / install / list) — the round-trip

**Files:**
- Create: `dothub/app/setups.py`
- Test: `dothub/tests/test_roundtrip.py`

**Interfaces:**
- Consumes: `app.models`, `app.bundle`, `app.storage`, an SQLAlchemy `Session`, a `User` instance.
- Produces: `OwnershipError(Exception)`, `NotFound(Exception)`; `publish(db, owner, title, description, files, slug=None) -> dict` (`{slug, version, url}`); `preview(db, slug) -> dict` (`{slug, title, description, version, effects, files: list[str]}`); `install(db, slug) -> dict` (`{slug, version, files: dict, effects: dict}`); `list_setups(db, query=None, limit=50) -> list[dict]` (`{slug, title, description, downloads, runs_code}`).

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_roundtrip.py`:
```python
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
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_roundtrip.py -v`
Expected: FAIL — `app.setups` missing.

- [ ] **Step 3: Write `setups.py`**

```python
from sqlalchemy import select
from .config import settings
from .models import Setup, SetupVersion, User
from . import bundle, storage

class OwnershipError(Exception):
    pass

class NotFound(Exception):
    pass

def _load_latest(db, slug: str) -> tuple[Setup, SetupVersion]:
    s = db.scalar(select(Setup).where(Setup.slug == slug))
    if not s:
        raise NotFound(slug)
    v = db.scalar(
        select(SetupVersion)
        .where(SetupVersion.setup_id == s.id, SetupVersion.version == s.latest_version)
    )
    return s, v

def publish(db, owner: User, title: str, description: str, files: dict, slug: str | None = None) -> dict:
    bundle.validate_files(files, settings.max_bundle_bytes)
    manifest = bundle.effects_manifest(files)
    manifest["title"] = title
    manifest["description"] = description
    archive = bundle.pack(files)
    slug = slug or bundle.slugify(title)

    existing = db.scalar(select(Setup).where(Setup.slug == slug))
    if existing and existing.owner_id != owner.id:
        raise OwnershipError(slug)

    if existing:
        version = existing.latest_version + 1
        existing.latest_version = version
        existing.title = title
        existing.description = description
        setup = existing
    else:
        version = 1
        setup = Setup(owner_id=owner.id, slug=slug, title=title,
                      description=description, latest_version=1)
        db.add(setup)
        db.flush()

    key = f"{slug}/v{version}.tar.gz"
    storage.put_archive(key, archive)
    db.add(SetupVersion(setup_id=setup.id, version=version, manifest_json=manifest,
                        archive_key=key, size_bytes=len(archive)))
    db.commit()
    return {"slug": slug, "version": version, "url": f"{settings.base_url}/s/{slug}"}

def preview(db, slug: str) -> dict:
    s, v = _load_latest(db, slug)
    files = bundle.unpack(storage.get_archive(v.archive_key))
    return {
        "slug": s.slug, "title": s.title, "description": s.description,
        "version": v.version, "effects": v.manifest_json, "files": sorted(files),
    }

def install(db, slug: str) -> dict:
    s, v = _load_latest(db, slug)
    files = bundle.unpack(storage.get_archive(v.archive_key))
    s.downloads += 1
    db.commit()
    return {"slug": s.slug, "version": v.version, "files": files, "effects": v.manifest_json}

def list_setups(db, query: str | None = None, limit: int = 50) -> list[dict]:
    stmt = select(Setup, SetupVersion).join(
        SetupVersion,
        (SetupVersion.setup_id == Setup.id) & (SetupVersion.version == Setup.latest_version),
    ).where(Setup.is_public.is_(True))
    if query:
        stmt = stmt.where(Setup.title.ilike(f"%{query}%"))
    stmt = stmt.order_by(Setup.downloads.desc(), Setup.created_at.desc()).limit(limit)
    out = []
    for s, v in db.execute(stmt).all():
        out.append({
            "slug": s.slug, "title": s.title, "description": s.description,
            "downloads": s.downloads, "runs_code": bool(v.manifest_json.get("runs_code")),
        })
    return out
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_roundtrip.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add dothub/app/setups.py dothub/tests/test_roundtrip.py
git commit -m "feat: core publish/preview/install/list logic with effects manifest"
```

---

### Task 7: REST API + auth routes

**Files:**
- Create: `dothub/app/api.py`
- Modify: `dothub/app/main.py` (add SessionMiddleware + include router)
- Test: `dothub/tests/test_api.py`

**Interfaces:**
- Consumes: `app.setups`, `app.security`, `app.models`, `app.db.get_session`.
- Produces: an `APIRouter` named `router`; dependency `current_user(request, db) -> User`.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_api.py`:
```python
def test_signup_login_key_publish_flow(client, s3):
    # signup logs the user in (session cookie kept by TestClient)
    r = client.post("/api/signup", json={"username": "cata", "email": "c@x.com", "password": "pw"})
    assert r.status_code == 200

    r = client.post("/api/keys", json={"label": "cli"})
    assert r.status_code == 200
    key = r.json()["api_key"]
    assert key.startswith("dh_")

    # publish via API key (Bearer)
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"title": "My Flow", "description": "d",
                          "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
    assert r.json()["slug"] == "my-flow"

    r = client.get("/api/setups")
    assert any(s["slug"] == "my-flow" for s in r.json())

def test_publish_requires_auth(client, s3):
    r = client.post("/api/setups", json={"title": "X", "description": "", "files": {"a.md": "1"}})
    assert r.status_code == 401

def test_duplicate_signup_rejected(client, s3):
    client.post("/api/signup", json={"username": "a", "email": "a@x.com", "password": "p"})
    r = client.post("/api/signup", json={"username": "a", "email": "a@x.com", "password": "p"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_api.py -v`
Expected: FAIL — routes missing (404/none).

- [ ] **Step 3: Write `api.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_session
from .models import User, ApiKey
from . import security, setups

router = APIRouter()

class SignupIn(BaseModel):
    username: str
    email: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class KeyIn(BaseModel):
    label: str = ""

class PublishIn(BaseModel):
    title: str
    description: str = ""
    slug: str | None = None
    files: dict[str, str]

def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    # 1) Bearer API key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        kh = security.hash_api_key(auth.split(" ", 1)[1].strip())
        ak = db.scalar(select(ApiKey).where(ApiKey.key_hash == kh))
        if ak:
            return db.get(User, ak.user_id)
    # 2) session cookie
    uid = request.session.get("uid")
    if uid:
        u = db.get(User, uid)
        if u:
            return u
    raise HTTPException(status_code=401, detail="authentication required")

@router.post("/api/signup")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_session)):
    exists = db.scalar(select(User).where((User.username == body.username) | (User.email == body.email)))
    if exists:
        raise HTTPException(status_code=400, detail="username or email taken")
    u = User(username=body.username, email=body.email,
             password_hash=security.hash_password(body.password))
    db.add(u); db.commit()
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_session)):
    u = db.scalar(select(User).where(User.email == body.email))
    if not u or not security.verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/keys")
def mint_key(body: KeyIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    plain, key_hash = security.generate_api_key()
    db.add(ApiKey(user_id=user.id, key_hash=key_hash, label=body.label)); db.commit()
    return {"api_key": plain}  # shown once

@router.get("/api/setups")
def api_list(q: str | None = None, db: Session = Depends(get_session)):
    return setups.list_setups(db, query=q)

@router.get("/api/setups/{slug}")
def api_get(slug: str, db: Session = Depends(get_session)):
    try:
        return setups.preview(db, slug)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")

@router.post("/api/setups")
def api_publish(body: PublishIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        return setups.publish(db, user, body.title, body.description, body.files, body.slug)
    except setups.OwnershipError:
        raise HTTPException(status_code=403, detail="slug owned by another user")

@router.get("/api/setups/{slug}/download")
def api_download(slug: str, db: Session = Depends(get_session)):
    from .storage import presign_get
    try:
        res = setups.install(db, slug)  # increments downloads
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
    s, v = setups._load_latest(db, slug)
    return {"url": presign_get(v.archive_key), "version": res["version"]}
```

- [ ] **Step 4: Wire router + session middleware into `main.py`**

Replace `main.py` with:
```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from .db import init_db
from .config import settings
from .api import router as api_router

def create_app() -> FastAPI:
    app = FastAPI(title="dothub")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

    @app.on_event("startup")
    def _startup():
        init_db()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(api_router)
    return app

app = create_app()
```

- [ ] **Step 5: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_api.py tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add dothub/app/api.py dothub/app/main.py dothub/tests/test_api.py
git commit -m "feat: REST API (signup/login/keys/setups) with session+bearer auth"
```

---

### Task 8: HTML feed + setup detail (effects rendered prominently)

**Files:**
- Create: `dothub/app/templates/feed.html`
- Create: `dothub/app/templates/detail.html`
- Modify: `dothub/app/api.py` (add `/` and `/s/{slug}` HTML routes + Jinja2)
- Test: `dothub/tests/test_html.py`

**Interfaces:**
- Consumes: `setups.list_setups`, `setups.preview`.
- Produces: `GET /` (feed), `GET /s/{slug}` (detail). Detail page must render each hook command verbatim and a responsibility notice.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_html.py`:
```python
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
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_html.py -v`
Expected: FAIL — HTML routes missing.

- [ ] **Step 3: Write `templates/feed.html`**

```html
<!doctype html><html><head><meta charset="utf-8"><title>dothub</title>
<style>body{font:16px system-ui;max-width:760px;margin:40px auto;padding:0 16px}
.card{border:1px solid #e5e5e5;border-radius:10px;padding:16px;margin:12px 0}
.warn{color:#b45309;font-size:13px}</style></head><body>
<h1>dothub — agent setups</h1>
{% for s in setups %}
  <div class="card">
    <a href="/s/{{ s.slug }}"><strong>{{ s.title }}</strong></a>
    — {{ s.downloads }} pulls
    {% if s.runs_code %}<span class="warn">⚠ runs code</span>{% endif %}
    <div>{{ s.description }}</div>
  </div>
{% endfor %}
</body></html>
```

- [ ] **Step 4: Write `templates/detail.html`**

```html
<!doctype html><html><head><meta charset="utf-8"><title>{{ p.title }} — dothub</title>
<style>body{font:16px system-ui;max-width:760px;margin:40px auto;padding:0 16px}
code{background:#f3f3f5;padding:2px 5px;border-radius:4px}
.notice{background:#fff8ec;border:1px solid #f1d9a8;padding:12px;border-radius:8px;color:#7c4a02}
pre{background:#0f0f14;color:#e7e7f2;padding:12px;border-radius:8px;overflow:auto}</style>
</head><body>
<a href="/">← feed</a>
<h1>{{ p.title }} <small>v{{ p.version }}</small></h1>
<p>{{ p.description }}</p>

<h3>What this setup does</h3>
{% if p.effects.runs_code %}
<div class="notice"><strong>⚠ This setup runs code.</strong> Review the exact commands below before installing.
You are responsible for verifying it is safe — dothub shows effects but does not vet them.</div>
{% else %}
<div class="notice">No hooks or MCP servers. Still your responsibility to review before installing.</div>
{% endif %}

{% if p.effects.hooks %}<h4>Hooks</h4><ul>
{% for h in p.effects.hooks %}<li>{{ h.event }}: <code>{{ h.command }}</code></li>{% endfor %}
</ul>{% endif %}

{% if p.effects.mcp_servers %}<h4>MCP servers</h4><ul>
{% for m in p.effects.mcp_servers %}<li>{{ m.name }}: <code>{{ m.command }} {{ m.args|join(' ') }}</code></li>{% endfor %}
</ul>{% endif %}

<h4>Files</h4><pre>{% for f in p.files %}{{ f }}
{% endfor %}</pre>
</body></html>
```

- [ ] **Step 5: Add HTML routes to `api.py`**

Append to `dothub/app/api.py` (after the imports, add the Jinja import; at the end add the routes):
```python
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@router.get("/", response_class=HTMLResponse)
def html_feed(request: Request, db: Session = Depends(get_session)):
    return templates.TemplateResponse("feed.html", {"request": request, "setups": setups.list_setups(db)})

@router.get("/s/{slug}", response_class=HTMLResponse)
def html_detail(slug: str, request: Request, db: Session = Depends(get_session)):
    try:
        p = setups.preview(db, slug)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
    return templates.TemplateResponse("detail.html", {"request": request, "p": p})
```

- [ ] **Step 6: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_html.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dothub/app/templates dothub/app/api.py dothub/tests/test_html.py
git commit -m "feat: HTML feed and detail page with prominent effects + responsibility notice"
```

---

### Task 9: Remote MCP server (FastMCP tools)

**Files:**
- Create: `dothub/app/mcp_server.py`
- Modify: `dothub/app/main.py` (mount the MCP ASGI app at `/mcp`)
- Test: `dothub/tests/test_mcp.py`

**Interfaces:**
- Consumes: `app.setups`, `app.security`, `app.models`, `app.db.SessionLocal`.
- Produces: module functions `publish_setup`, `preview_setup`, `install_setup`, `list_setups` (the FastMCP tool bodies, importable for direct unit testing); `mcp` (FastMCP instance); `get_mcp_app()` returning the ASGI app to mount.
- Note: tools authenticate by reading `Authorization: Bearer <key>` from the HTTP request via `_user_from_headers(db)`. Confirm `fastmcp.server.dependencies.get_http_headers` exists in the pinned FastMCP version; if the import path differs, adjust only that one import.

- [ ] **Step 1: Write the failing test**

`dothub/tests/test_mcp.py` (tests the tool bodies directly, passing the auth key explicitly via a monkeypatched header reader):
```python
def test_mcp_publish_and_install(db, s3, monkeypatch):
    from app.models import User, ApiKey
    from app import security, mcp_server

    u = User(username="cata", email="c@x.com", password_hash="x"); db.add(u); db.commit()
    plain, kh = security.generate_api_key()
    db.add(ApiKey(user_id=u.id, key_hash=kh)); db.commit()

    # make the tool use our test db session + our auth key
    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: plain)

    res = mcp_server.publish_setup("My Flow", "d", {"CLAUDE.md": "x"})
    assert res["slug"] == "my-flow"

    prev = mcp_server.preview_setup("my-flow")
    assert prev["effects"]["runs_code"] is False

    inst = mcp_server.install_setup("my-flow")
    assert inst["files"] == {"CLAUDE.md": "x"}

    listing = mcp_server.list_setups()
    assert any(s["slug"] == "my-flow" for s in listing)

def test_mcp_publish_requires_key(db, s3, monkeypatch):
    from app import mcp_server
    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: None)
    import pytest
    with pytest.raises(PermissionError):
        mcp_server.publish_setup("X", "", {"a.md": "1"})
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd dothub && pytest tests/test_mcp.py -v`
Expected: FAIL — `app.mcp_server` missing.

- [ ] **Step 3: Write `mcp_server.py`**

```python
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from sqlalchemy import select
from .db import SessionLocal
from .models import User, ApiKey
from . import security, setups

mcp = FastMCP("dothub")

def _open_session():
    return SessionLocal()

def _bearer_key():
    headers = get_http_headers()
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None

def _require_user(db) -> User:
    key = _bearer_key()
    if not key:
        raise PermissionError("missing API key")
    ak = db.scalar(select(ApiKey).where(ApiKey.key_hash == security.hash_api_key(key)))
    if not ak:
        raise PermissionError("invalid API key")
    return db.get(User, ak.user_id)

@mcp.tool
def publish_setup(title: str, description: str, files: dict[str, str], slug: str | None = None) -> dict:
    """Publish the caller's Claude Code setup. `files` is {relative_path: text_content}."""
    db = _open_session()
    try:
        user = _require_user(db)
        return setups.publish(db, user, title, description, files, slug)
    finally:
        db.close()

@mcp.tool
def preview_setup(slug: str) -> dict:
    """Return the effects manifest + file list for a setup, WITHOUT installing. Show this to the user first."""
    db = _open_session()
    try:
        return setups.preview(db, slug)
    finally:
        db.close()

@mcp.tool
def install_setup(slug: str) -> dict:
    """Return a setup's files + effects so the agent can write them locally AFTER user approval."""
    db = _open_session()
    try:
        return setups.install(db, slug)
    finally:
        db.close()

@mcp.tool
def list_setups(query: str | None = None) -> list[dict]:
    """List public setups (includes a runs_code flag)."""
    db = _open_session()
    try:
        return setups.list_setups(db, query=query)
    finally:
        db.close()

def get_mcp_app():
    # ASGI app for mounting under the main FastAPI app at /mcp
    return mcp.http_app(path="/")
```

- [ ] **Step 4: Mount in `main.py`**

In `create_app()` (before `return app`), add:
```python
    from .mcp_server import get_mcp_app
    app.mount("/mcp", get_mcp_app())
```

- [ ] **Step 5: Run tests, expect pass**

Run: `cd dothub && pytest tests/test_mcp.py -v`
Expected: PASS.

- [ ] **Step 6: Run the FULL suite**

Run: `cd dothub && pytest -v`
Expected: every test PASS.

- [ ] **Step 7: Commit**

```bash
git add dothub/app/mcp_server.py dothub/app/main.py dothub/tests/test_mcp.py
git commit -m "feat: remote MCP server with publish/preview/install/list tools"
```

---

### Task 10: Run locally + README

**Files:**
- Create: `dothub/README.md`
- Create: `dothub/.env.example`

**Interfaces:** none (documentation + manual smoke test).

- [ ] **Step 1: Write `.env.example`**

```
DATABASE_URL=postgresql+psycopg://dothub:CHANGEME@localhost:5432/dothub
S3_BUCKET=dothub-bundles
AWS_REGION=us-east-1
BASE_URL=https://your-domain.example
SESSION_SECRET=generate-a-long-random-string
MAX_BUNDLE_BYTES=5242880
```

- [ ] **Step 2: Write `README.md`**

````markdown
# dothub — agent setup hub

Publish your whole Claude Code setup, browse a public feed, pull setups in.
Remote MCP server + web feed in one FastAPI app.

## Run locally
```bash
pip install -r requirements.txt
export $(grep -v '^#' .env.example | xargs)   # or set real values
uvicorn app.main:app --reload
```
- Feed: http://localhost:8000/
- MCP:  http://localhost:8000/mcp/
- Health: http://localhost:8000/healthz

## Test
```bash
pytest -v          # uses in-memory SQLite + mocked S3, no infra needed
```

## Add to Claude Code (agent self-push)
Add the remote MCP server with your API key (minted at `POST /api/keys`):
```
claude mcp add --transport http dothub https://your-domain.example/mcp/ \
  --header "Authorization: Bearer dh_your_key"
```
Then: "publish my setup as my-flow" / "preview some-user/their-slug before installing".
````

- [ ] **Step 3: Manual smoke test**

Run: `cd dothub && uvicorn app.main:app` (with a local Postgres + real/minio S3, or SQLite + moto-less local), then:
`curl localhost:8000/healthz` → `{"status":"ok"}` and open `http://localhost:8000/`.
Expected: health ok, empty feed renders.

- [ ] **Step 4: Commit**

```bash
git add dothub/README.md dothub/.env.example
git commit -m "docs: README and env example"
```

---

### Task 11: AWS deployment runbook (EC2 + RDS + S3 + Nginx + certbot)

**Files:**
- Create: `dothub/deploy/dothub.service`
- Create: `dothub/deploy/nginx.conf`
- Create: `dothub/deploy/DEPLOY.md`

**Interfaces:** none (ops runbook; not TDD). Deliverable verified by the final smoke test in DEPLOY.md.

- [ ] **Step 1: Write `deploy/dothub.service` (systemd unit)**

```ini
[Unit]
Description=dothub
After=network.target

[Service]
User=dothub
WorkingDirectory=/opt/dothub
EnvironmentFile=/opt/dothub/.env
ExecStart=/opt/dothub/venv/bin/gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker -w 3 -b 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `deploy/nginx.conf`**

```nginx
server {
    listen 80;
    server_name your-domain.example;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # MCP uses Streamable HTTP — disable buffering for the /mcp path
    location /mcp/ {
        proxy_pass http://127.0.0.1:8000/mcp/;
        proxy_buffering off;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] **Step 3: Write `deploy/DEPLOY.md`**

````markdown
# AWS deployment runbook

## 1. S3
- Create bucket `dothub-bundles` (block public access ON — access only via the app's IAM role).

## 2. RDS
- Postgres instance, db `dothub`. Note the endpoint.
- Security group `sg-rds`: inbound 5432 **only** from `sg-app` (below).

## 3. EC2
- Ubuntu instance. Security group `sg-app`: inbound 22 from *your IP only*, 80+443 from anywhere.
- Attach an **IAM instance role** with `s3:GetObject`/`s3:PutObject` on `arn:aws:s3:::dothub-bundles/*`.

## 4. App
```bash
sudo useradd -m -d /opt/dothub dothub
sudo -u dothub git clone <repo> /opt/dothub && cd /opt/dothub
sudo -u dothub python3 -m venv venv && sudo -u dothub venv/bin/pip install -r requirements.txt
# write /opt/dothub/.env from .env.example (DATABASE_URL → RDS, S3_BUCKET, BASE_URL=https://your-domain, SESSION_SECRET)
sudo cp deploy/dothub.service /etc/systemd/system/ && sudo systemctl enable --now dothub
```

## 5. Nginx + TLS
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/dothub
sudo ln -s /etc/nginx/sites-available/dothub /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.example   # provisions + auto-renews TLS
```

## 6. Smoke test (the deliverable)
```bash
curl https://your-domain.example/healthz          # → {"status":"ok"}
# signup, mint a key, publish, confirm it appears on the feed:
curl -s -X POST https://your-domain.example/api/signup -H 'content-type: application/json' \
  -d '{"username":"me","email":"me@x.com","password":"pw"}' -c jar
KEY=$(curl -s -X POST https://your-domain.example/api/keys -b jar -H 'content-type: application/json' -d '{"label":"cli"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["api_key"])')
curl -s -X POST https://your-domain.example/api/setups -H "Authorization: Bearer $KEY" \
  -H 'content-type: application/json' -d '{"title":"Smoke","description":"","files":{"CLAUDE.md":"hi"}}'
curl -s https://your-domain.example/api/setups   # → includes "smoke"
```
Expected: health ok; publish returns a slug; feed lists it; `https://your-domain.example/s/smoke` renders with the responsibility notice.
````

- [ ] **Step 4: Commit**

```bash
git add dothub/deploy
git commit -m "docs: AWS deployment runbook (systemd, nginx, certbot, RDS, S3, IAM)"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** accounts+password (T2,T5,T7) · API keys (T5,T7) · publish/versioning (T6) · S3 storage (T4,T6) · effects manifest (T3,T6, rendered T8, previewed T9) · feed+detail (T8) · transparency-first install via `preview_setup` + detail notice (T8,T9) · agent self-push (T9) · AWS deploy (T11) · path-traversal/size guards (T3) · slug ownership 403 (T6,T7). All spec sections map to a task.
- **Placeholder scan:** no TBD/TODO; every code step contains complete code.
- **Type consistency:** `publish/preview/install/list_setups` signatures identical across T6, T7, T9; `effects_manifest` keys (`hooks/mcp_servers/counts/runs_code/secret_flags`) consistent across T3, T6, T8. `generate_api_key()->(plain, key_hash)` and `hash_api_key` used consistently in T5, T7, T9.
- **Known external-lib risk:** FastMCP `get_http_headers` import path + `mcp.http_app()` signature should be confirmed against the pinned `fastmcp` version (flagged in Task 9 interfaces). Everything else uses stable stdlib/FastAPI/SQLAlchemy/boto3 APIs.
