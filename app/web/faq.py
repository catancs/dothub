from fastapi import APIRouter, Depends, Request

from app.api import optional_user
from app.web._render import render

router = APIRouter()

# The GET /faq route is implemented by the FAQ workstream. This stub keeps the
# router registration in app/web/__init__.py stable so that workstream never has
# to edit the shared router-wiring file.


@router.get("/faq")
def faq_page(request: Request, user=Depends(optional_user)):
    return render(request, "faq.html", {}, user=user)
