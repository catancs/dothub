from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, literal
from .config import settings
from .models import Setup, SetupVersion, User, PullEvent, Follow
from . import bundle, storage

class OwnershipError(Exception):
    pass

class NotFound(Exception):
    pass

def _now() -> datetime:
    return datetime.now(timezone.utc)

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

def preview(db, slug: str, include_files: bool = False) -> dict:
    s, v = _load_latest(db, slug)
    author = db.scalar(select(User.username).where(User.id == s.owner_id))
    files = bundle.unpack(storage.get_archive(v.archive_key))
    out = {
        "slug": s.slug, "title": s.title, "description": s.description,
        "version": v.version, "effects": v.manifest_json, "files": sorted(files),
        "author": author,
    }
    if include_files:
        out["file_contents"] = files
    return out

def revert(db, user: User, slug: str, target_version: int) -> dict:
    s = db.scalar(select(Setup).where(Setup.slug == slug))
    if not s:
        raise NotFound(slug)
    if s.owner_id != user.id:
        raise OwnershipError(slug)
    target = db.scalar(select(SetupVersion).where(
        SetupVersion.setup_id == s.id, SetupVersion.version == target_version))
    if not target:
        raise NotFound(f"{slug} v{target_version}")
    new_version = s.latest_version + 1
    data = storage.get_archive(target.archive_key)
    new_key = f"{slug}/v{new_version}.tar.gz"
    storage.put_archive(new_key, data)
    db.add(SetupVersion(setup_id=s.id, version=new_version,
                        manifest_json=target.manifest_json, archive_key=new_key,
                        size_bytes=target.size_bytes))
    s.latest_version = new_version
    db.commit()
    return {"slug": slug, "version": new_version, "reverted_from": target_version}

def install(db, slug: str, user: User | None = None) -> dict:
    s, v = _load_latest(db, slug)
    files = bundle.unpack(storage.get_archive(v.archive_key))
    s.downloads += 1
    if user is not None:
        db.add(PullEvent(user_id=user.id, setup_id=s.id, version=v.version))
    db.commit()
    return {"slug": s.slug, "version": v.version, "files": files, "effects": v.manifest_json}

def list_setups(db, query: str | None = None, limit: int = 50,
                window: str | None = None, following_of: User | None = None) -> list[dict]:
    stmt = select(Setup, SetupVersion, User.username).join(
        SetupVersion,
        (SetupVersion.setup_id == Setup.id) & (SetupVersion.version == Setup.latest_version),
    ).join(User, User.id == Setup.owner_id).where(Setup.is_public.is_(True))
    if query:
        stmt = stmt.where(Setup.title.ilike(f"%{query}%"))

    delta = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}.get(window)
    since = _now() - delta if delta else None
    if since is not None:
        pc = (select(PullEvent.setup_id, func.count().label("c"))
              .where(PullEvent.created_at >= since)
              .group_by(PullEvent.setup_id).subquery())
        stmt = stmt.add_columns(func.coalesce(pc.c.c, 0).label("recent")).outerjoin(
            pc, pc.c.setup_id == Setup.id)
    else:
        stmt = stmt.add_columns(literal(0).label("recent"))

    if following_of is not None:
        followee_ids = select(Follow.followee_id).where(Follow.follower_id == following_of.id)
        stmt = stmt.where(Setup.owner_id.in_(followee_ids)).order_by(Setup.created_at.desc())
    elif since is not None:
        stmt = stmt.order_by(func.coalesce(pc.c.c, 0).desc(), Setup.downloads.desc())
    else:
        stmt = stmt.order_by(Setup.downloads.desc(), Setup.created_at.desc())

    out = []
    for s, v, username, recent in db.execute(stmt.limit(limit)).all():
        out.append({
            "slug": s.slug, "title": s.title, "description": s.description,
            "downloads": s.downloads, "recent_pulls": recent,
            "runs_code": bool(v.manifest_json.get("runs_code")),
            "author": username,
        })
    return out
