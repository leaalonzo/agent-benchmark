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

_GITHUB_API = "https://api.github.com/search/repositories"
logger = logging.getLogger(__name__)


def github_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    token = os.environ.get("GITHUB_TOKEN", "")
    params = urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": max_results}
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("GITHUB_TOKEN not set — rate limit is 10 req/min unauthenticated")

    req = urllib.request.Request(f"{_GITHUB_API}?{params}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            if remaining != "?" and int(remaining) < 5:
                logger.warning("GitHub rate limit low: %s requests remaining", remaining)
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        logger.warning("GitHub API HTTP error %s: %s", exc.code, exc.reason)
        return []
    except Exception as exc:
        logger.warning("GitHub API request failed: %s", exc)
        return []

    results = []
    for repo in data.get("items", [])[:max_results]:
        results.append(
            {
                "name": repo.get("name", ""),
                "full_name": repo.get("full_name", ""),
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url", ""),
                "language": repo.get("language", ""),
                "updated_at": repo.get("updated_at", ""),
            }
        )
    return results
