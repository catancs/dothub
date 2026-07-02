from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .db import init_db
from .config import settings
from .api import router as api_router
from .web import router as web_router
from .mcp_server import get_mcp_app


def create_app() -> FastAPI:
    mcp_app = get_mcp_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize our DB, then enter the MCP app's lifespan so its session
        # manager is started (required for /mcp requests to work).
        init_db()
        async with mcp_app.lifespan(app):
            yield

    app = FastAPI(title="dothub", lifespan=lifespan)
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from .ratelimit import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Secure cookie in production (BASE_URL is https); relaxed over plain http
    # for local dev and the test client, which cannot send a Secure cookie back.
    session_https_only = settings.base_url.startswith("https")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret,
                       https_only=session_https_only, same_site="lax")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    app.mount("/mcp", mcp_app)
    return app


app = create_app()
