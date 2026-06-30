from fastapi import FastAPI
from .db import init_db

def create_app() -> FastAPI:
    app = FastAPI(title="dothub")

    @app.on_event("startup")
    def _startup():
        init_db()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

app = create_app()
