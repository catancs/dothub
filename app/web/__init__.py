from fastapi import APIRouter

from . import feed, detail, history, account, auth, publish

router = APIRouter()
router.include_router(feed.router)
router.include_router(detail.router)
router.include_router(history.router)
router.include_router(account.router)
router.include_router(auth.router)
router.include_router(publish.router)
