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
    author = db.scalar(select(User.username).where(User.id == s.owner_id))
    files = bundle.unpack(storage.get_archive(v.archive_key))
    return {
        "slug": s.slug, "title": s.title, "description": s.description,
        "version": v.version, "effects": v.manifest_json, "files": sorted(files),
        "author": author,
    }

def install(db, slug: str) -> dict:
    s, v = _load_latest(db, slug)
    files = bundle.unpack(storage.get_archive(v.archive_key))
    s.downloads += 1
    db.commit()
    return {"slug": s.slug, "version": v.version, "files": files, "effects": v.manifest_json}

def list_setups(db, query: str | None = None, limit: int = 50) -> list[dict]:
    stmt = select(Setup, SetupVersion, User.username).join(
        SetupVersion,
        (SetupVersion.setup_id == Setup.id) & (SetupVersion.version == Setup.latest_version),
    ).join(User, User.id == Setup.owner_id).where(Setup.is_public.is_(True))
    if query:
        stmt = stmt.where(Setup.title.ilike(f"%{query}%"))
    stmt = stmt.order_by(Setup.downloads.desc(), Setup.created_at.desc()).limit(limit)
    out = []
    for s, v, username in db.execute(stmt).all():
        out.append({
            "slug": s.slug, "title": s.title, "description": s.description,
            "downloads": s.downloads, "runs_code": bool(v.manifest_json.get("runs_code")),
            "author": username,
        })
    return out
