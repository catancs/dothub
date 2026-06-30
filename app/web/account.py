from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api import optional_user
from app.db import get_session
from app.models import User, Setup, SetupVersion, ApiKey, Follow, PullEvent
from ._render import render

router = APIRouter()


def _counts(db: Session, target: User) -> dict:
    followers = db.scalar(
        select(func.count()).select_from(Follow).where(Follow.followee_id == target.id)
    )
    following = db.scalar(
        select(func.count()).select_from(Follow).where(Follow.follower_id == target.id)
    )
    setups_count = db.scalar(
        select(func.count()).select_from(Setup).where(Setup.owner_id == target.id)
    )
    pulls = db.scalar(
        select(func.count()).select_from(PullEvent).where(PullEvent.user_id == target.id)
    )
    return {
        "followers": followers or 0,
        "following": following or 0,
        "setups": setups_count or 0,
        "pulls": pulls or 0,
    }


def _setups_with_flags(db: Session, owner: User) -> list[dict]:
    rows = db.scalars(select(Setup).where(Setup.owner_id == owner.id)).all()
    out = []
    for s in rows:
        latest = db.scalar(
            select(SetupVersion)
            .where(SetupVersion.setup_id == s.id)
            .order_by(SetupVersion.version.desc())
        )
        runs_code = bool(latest.manifest_json.get("runs_code")) if latest else False
        out.append({"setup": s, "runs_code": runs_code})
    return out


@router.get("/account")
def account_page(request: Request, db: Session = Depends(get_session)):
    user = optional_user(request, db)
    if user is None:
        return RedirectResponse("/login", 303)
    counts = _counts(db, user)
    keys = db.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    ).all()
    setups = _setups_with_flags(db, user)
    return render(
        request,
        "account.html",
        {"profile": user, "counts": counts, "keys": keys, "setups": setups},
        user=user,
    )


@router.post("/account")
def account_update(
    request: Request,
    display_name: str = Form(""),
    bio: str = Form(""),
    link_github: str = Form(""),
    link_linkedin: str = Form(""),
    link_x: str = Form(""),
    db: Session = Depends(get_session),
):
    user = optional_user(request, db)
    if user is None:
        return RedirectResponse("/login", 303)
    user.display_name = display_name or None
    user.bio = bio or None
    user.link_github = link_github or None
    user.link_linkedin = link_linkedin or None
    user.link_x = link_x or None
    db.commit()
    return RedirectResponse("/account", 303)


@router.get("/u/{username}")
def profile_page(username: str, request: Request, db: Session = Depends(get_session)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None:
        raise HTTPException(status_code=404, detail="no such user")
    viewer = optional_user(request, db)
    counts = _counts(db, target)
    setups = [
        item
        for item in _setups_with_flags(db, target)
        if item["setup"].is_public
    ]
    is_following = False
    if viewer is not None and viewer.id != target.id:
        is_following = (
            db.scalar(
                select(Follow).where(
                    Follow.follower_id == viewer.id, Follow.followee_id == target.id
                )
            )
            is not None
        )
    is_self = viewer is not None and viewer.id == target.id
    return render(
        request,
        "profile.html",
        {
            "profile": target,
            "counts": counts,
            "setups": setups,
            "is_following": is_following,
            "is_self": is_self,
            "can_follow": viewer is not None and not is_self,
        },
        user=viewer,
    )
