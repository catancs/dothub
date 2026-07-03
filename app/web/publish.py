from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.api import optional_user
from app.mcp_server import PUBLISHING_GUIDE
from app.web._render import render

router = APIRouter()


@router.get("/publish")
def publish_page(request: Request, user=Depends(optional_user)):
    return render(request, "publish.html", {}, user=user)


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    # ponytail: same guide the MCP server sends as instructions; agents that
    # land on the website instead of MCP get the identical canonical spec.
    return PUBLISHING_GUIDE
