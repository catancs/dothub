from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_key(request):
    """Use the real client IP behind nginx (X-Forwarded-For), else the peer."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=rate_key)
