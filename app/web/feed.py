from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db import get_session
from app.api import optional_user
from app import setups
from app.web._render import render

router = APIRouter()


@router.get("/")
def feed(request: Request, tab: str = "discover", window: str = "7d",
         db: Session = Depends(get_session), user=Depends(optional_user)):
    if tab == "following":
        if user is None:
            return RedirectResponse("/login", status_code=303)
        items = setups.list_setups(db, following_of=user)
    else:
        items = setups.list_setups(db, window=window)
    return render(request, "feed.html", {"items": items, "tab": tab, "window": window}, user=user)
