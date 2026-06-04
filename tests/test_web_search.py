import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.web_search import web_search

REQUIRED_KEYS = {"title", "url", "description", "published_date"}


def test_web_search_returns_results():
    results = web_search("Hermes Agent Nous Research", num_results=5)
    assert isinstance(results, list), "Result must be a list"
    if not os.environ.get("BRAVE_API_KEY"):
        print("SKIP — BRAVE_API_KEY not set")
        return
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    for item in results:
        missing = REQUIRED_KEYS - item.keys()
        assert not missing, f"Result missing keys: {missing}\nItem: {item}"


if __name__ == "__main__":
    test_web_search_returns_results()
    results = web_search("Hermes Agent Nous Research", num_results=5)
    print(f"PASS — got {len(results)} results")
