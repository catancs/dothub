from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db import get_session
from app.api import optional_user
from app import setups, bundle
from app.web._render import render

router = APIRouter()


@router.get("/")
def feed(request: Request, tab: str = "discover", window: str = "7d",
         q: str | None = None,
         db: Session = Depends(get_session), user=Depends(optional_user)):
    if tab == "following":
        if user is None:
            return RedirectResponse("/login", status_code=303)
        items = setups.list_setups(db, following_of=user)
    elif tab == "no-code":
        items = setups.list_setups(db, window=window, runs_code=False)
    else:
        items = setups.list_setups(db, query=q, window=window)
    for it in items:
        it["primary_tag"] = bundle.primary_tag({"runs_code": it["runs_code"], "tags": it.get("tags", [])})
    return render(request, "feed.html",
                  {"items": items, "tab": tab, "window": window, "q": q or ""}, user=user)
