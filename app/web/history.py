from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api import optional_user
from ..db import get_session
from ..models import Setup, SetupVersion, PullEvent
from ._render import render

router = APIRouter()


@router.get("/history")
def history(request: Request, filter: str = "all",
            user=Depends(optional_user), db: Session = Depends(get_session)):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if filter not in ("all", "pushed", "pulled"):
        filter = "all"

    events: list[dict] = []

    pushes = db.execute(
        select(SetupVersion, Setup)
        .join(Setup, Setup.id == SetupVersion.setup_id)
        .where(Setup.owner_id == user.id)
    ).all()
    for v, s in pushes:
        events.append({
            "kind": "push",
            "slug": s.slug,
            "version": v.version,
            "at": v.created_at,
            "runs_code": bool((v.manifest_json or {}).get("runs_code")),
        })

    pulls = db.execute(
        select(PullEvent, Setup)
        .join(Setup, Setup.id == PullEvent.setup_id)
        .where(PullEvent.user_id == user.id)
    ).all()
    for pe, s in pulls:
        events.append({
            "kind": "pull",
            "slug": s.slug,
            "version": pe.version,
            "at": pe.created_at,
        })

    events.sort(key=lambda e: e["at"], reverse=True)

    if filter == "pushed":
        events = [e for e in events if e["kind"] == "push"]
    elif filter == "pulled":
        events = [e for e in events if e["kind"] == "pull"]

    return render(request, "history.html", {"events": events, "filter": filter}, user=user)
