import json
import logging
import os
import ssl
import urllib.parse
import urllib.request
from typing import Any


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
logger = logging.getLogger(__name__)


def web_search(query: str, num_results: int = 5) -> list[dict[str, Any]]:
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set — returning empty results")
        return []

    params = urllib.parse.urlencode({"q": query, "count": num_results})
    req = urllib.request.Request(
        f"{_BRAVE_URL}?{params}",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
            raw = resp.read()
            # urllib transparently decompresses gzip when Accept-Encoding is set
            # but urlopen doesn't decompress automatically; handle both
            try:
                data = json.loads(raw)
            except Exception:
                import gzip
                data = json.loads(gzip.decompress(raw))
    except urllib.error.HTTPError as exc:
        logger.warning("Brave API HTTP error %s: %s", exc.code, exc.reason)
        return []
    except Exception as exc:
        logger.warning("Brave API request failed: %s", exc)
        return []

    results = []
    for item in data.get("web", {}).get("results", [])[:num_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "published_date": item.get("page_age", ""),
            }
        )
    return results
