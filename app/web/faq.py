from fastapi import APIRouter

router = APIRouter()

# The GET /faq route is implemented by the FAQ workstream. This stub keeps the
# router registration in app/web/__init__.py stable so that workstream never has
# to edit the shared router-wiring file.
