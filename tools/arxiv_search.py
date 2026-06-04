import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

_NS = "http://www.w3.org/2005/Atom"
_ARXIV_API = "https://export.arxiv.org/api/query"
logger = logging.getLogger(__name__)


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_arxiv(
    topic: str,
    max_results: int = 10,
    retries: int = 3,
    backoff: float = 5.0,
) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(topic)
    url = (
        f"{_ARXIV_API}?search_query=all:{encoded}"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30, context=_ssl_ctx()) as resp:
                xml_bytes = resp.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = backoff * (attempt + 1)
                logger.warning("ArXiv 429 rate limit — waiting %.0fs (attempt %d/%d)", wait, attempt + 1, retries)
                time.sleep(wait)
                if attempt == retries - 1:
                    logger.warning("ArXiv rate limited after %d retries — returning empty", retries)
                    return []
            else:
                logger.warning("ArXiv HTTP error %s: %s", exc.code, exc.reason)
                return []
        except Exception as exc:
            logger.warning("ArXiv request failed: %s", exc)
            if attempt == retries - 1:
                return []
            time.sleep(backoff)
    else:
        return []

    root = ET.fromstring(xml_bytes)
    results = []
    for entry in root.findall(f"{{{_NS}}}entry"):
        authors = [
            a.findtext(f"{{{_NS}}}name", "").strip()
            for a in entry.findall(f"{{{_NS}}}author")
        ]
        arxiv_id_raw = entry.findtext(f"{{{_NS}}}id", "").strip()
        arxiv_id = arxiv_id_raw.rstrip("/").split("/")[-1]
        results.append(
            {
                "title": (entry.findtext(f"{{{_NS}}}title") or "").strip(),
                "authors": authors,
                "abstract": (entry.findtext(f"{{{_NS}}}summary") or "").strip(),
                "arxiv_id": arxiv_id,
                "url": arxiv_id_raw,
                "published": (entry.findtext(f"{{{_NS}}}published") or "").strip(),
            }
        )
    return results


def fetch_arxiv_batched(
    topics: list[str], max_results: int = 10, delay: float = 3.0
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for i, topic in enumerate(topics):
        if i > 0:
            time.sleep(delay)
        out[topic] = fetch_arxiv(topic, max_results)
    return out
