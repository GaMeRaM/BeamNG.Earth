"""OpenFreeMap resources for CEF maps, relayed through the existing game connection.

Only demand requests; no prefetch. The small in-memory LRU is shared by both maps.
"""
import base64
from functools import lru_cache
from urllib.parse import urlsplit

MAX_BYTES = 2 * 1024 * 1024


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Invalid map resource URL")
    p = urlsplit(url)
    if (p.scheme != "https" or p.netloc != "tiles.openfreemap.org"
            or p.fragment or "\\" in url or any(ord(c) < 32 for c in url)):
        raise ValueError("Only https://tiles.openfreemap.org resources are allowed")
    return url


@lru_cache(maxsize=64)
def resource(fetcher, url):
    validate_url(url)
    response = fetcher.get(url, kind="demand")
    if len(response.body) > MAX_BYTES:
        raise ValueError("Map resource exceeds 2 MiB")
    return base64.b64encode(response.body).decode("ascii")
