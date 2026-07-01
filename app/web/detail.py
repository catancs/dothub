from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api import optional_user
from ..db import get_session
from ..models import Setup, SetupVersion, User
from .. import setups
from ._render import render

router = APIRouter()

# Fixed display order for the Contents file browser.
_CAT_ORDER = ["Rules", "Skills", "Commands", "Agents", "Config", "Other"]


def _cat(path: str) -> str:
    if path == "CLAUDE.md" or path.startswith(".claude/rules/"):
        return "Rules"
    if path.startswith("skills/"):
        return "Skills"
    if path.startswith("commands/"):
        return "Commands"
    if path.startswith("agents/"):
        return "Agents"
    if path.startswith("hooks/") or path in (".mcp.json", "plugins.json"):
        return "Config"
    return "Other"


@router.get("/s/{slug}")
def detail(slug: str, request: Request,
           user: User | None = Depends(optional_user),
           db: Session = Depends(get_session)):
    try:
        p = setups.preview(db, slug, include_files=True)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")

    s = db.scalar(select(Setup).where(Setup.slug == slug))
    versions = db.scalars(
        select(SetupVersion)
        .where(SetupVersion.setup_id == s.id)
        .order_by(SetupVersion.version.desc())
    ).all()

    is_owner = bool(user and user.id == s.owner_id)

    # Group file contents by category, in the fixed order, skipping empties.
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(p["file_contents"]):
        by_cat.setdefault(_cat(path), []).append((path, p["file_contents"][path]))
    groups = [(cat, by_cat[cat]) for cat in _CAT_ORDER if cat in by_cat]

    readme = p["file_contents"].get("README.md")
    tags = p["effects"].get("tags", [])
    return render(request, "detail.html", {
        "p": p,
        "versions": versions,
        "is_owner": is_owner,
        "current": s.latest_version,
        "groups": groups,
        "readme": readme,
        "tags": tags,
    }, user=user)
