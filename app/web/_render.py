from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..agents import agent_info

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
# Expose the agent-provenance registry to all templates so feed/detail can
# render an icon+label from a setup's `agent` slug without route plumbing.
templates.env.globals["agent_info"] = agent_info


def render(request: Request, name: str, ctx: dict, user=None) -> HTMLResponse:
    ctx["request"] = request
    ctx["user"] = user
    return templates.TemplateResponse(request, name, ctx)
