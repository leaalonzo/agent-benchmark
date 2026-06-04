import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.github_search import github_search

REQUIRED_KEYS = {"name", "full_name", "description", "stars", "url", "language", "updated_at"}


def test_github_search_returns_results():
    results = github_search("AI agent framework", max_results=5)
    assert isinstance(results, list), "Result must be a list"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    for item in results:
        missing = REQUIRED_KEYS - item.keys()
        assert not missing, f"Result missing keys: {missing}\nItem: {item}"
        assert "stars" in item, "Must have stars key"


if __name__ == "__main__":
    test_github_search_returns_results()
    results = github_search("AI agent framework", max_results=5)
    print(f"PASS — got {len(results)} results")
    for r in results:
        print(f"  {r['full_name']} ({r['stars']} stars)")
