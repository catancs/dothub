from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def render(request: Request, name: str, ctx: dict, user=None) -> HTMLResponse:
    ctx["request"] = request
    ctx["user"] = user
    return templates.TemplateResponse(request, name, ctx)
