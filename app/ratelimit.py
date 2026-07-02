from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def rate_key(request):
    """Use the real client IP behind nginx (X-Forwarded-For), else the peer."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=rate_key)


def rate_limit_handler(request, exc: RateLimitExceeded):
    """Stock slowapi 429, plus the Retry-After header the spec requires.

    Every limit in this app is per-minute, so a fixed 60 second window is correct.
    We keep the limiter's headers_enabled at its default False: enabling it makes
    slowapi inject headers on the success path too, which crashes routes that do
    not declare a response parameter. Appending Retry-After only here, on the 429
    path, avoids that and leaves success responses untouched.
    """
    # ponytail: constant 60s; derive from exc.limit if limits ever vary by window.
    response = _rate_limit_exceeded_handler(request, exc)
    response.headers["Retry-After"] = "60"
    return response
