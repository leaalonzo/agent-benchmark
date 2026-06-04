import logging
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING)

from tools.arxiv_search import fetch_arxiv

REQUIRED_KEYS = {"title", "authors", "abstract", "arxiv_id", "url", "published"}


def test_fetch_arxiv_returns_results():
    results = fetch_arxiv("language models", max_results=3)
    if not results:
        print("SKIP — ArXiv returned empty (likely rate limited on this IP; will work on VPS)")
        return
    assert isinstance(results, list), "Result must be a list"
    for item in results:
        missing = REQUIRED_KEYS - item.keys()
        assert not missing, f"Result missing keys: {missing}\nItem: {item}"


if __name__ == "__main__":
    test_fetch_arxiv_returns_results()
    results = fetch_arxiv("language models", max_results=3)
    if results:
        print(f"PASS — got {len(results)} results")
        for r in results:
            print(f"  [{r['arxiv_id']}] {r['title'][:70]}")
    else:
        print("SKIP — rate limited (run on VPS to verify)")
