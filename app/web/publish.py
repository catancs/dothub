from fastapi import APIRouter, Depends, Request

from app.api import optional_user
from app.web._render import render

router = APIRouter()


@router.get("/publish")
def publish_page(request: Request, user=Depends(optional_user)):
    return render(request, "publish.html", {}, user=user)
