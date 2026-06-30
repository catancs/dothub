from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from .db import init_db
from .config import settings
from .api import router as api_router

def create_app() -> FastAPI:
    app = FastAPI(title="dothub")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

    @app.on_event("startup")
    def _startup():
        init_db()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(api_router)
    return app

app = create_app()
