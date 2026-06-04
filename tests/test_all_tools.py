"""
Run all three tools with BENCHMARK_TOPIC from .env for manual inspection.
Usage:
    python tests/test_all_tools.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env if present
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from tools.arxiv_search import fetch_arxiv
from tools.web_search import web_search
from tools.github_search import github_search

TOPIC = os.environ.get("BENCHMARK_TOPIC", "AI agent frameworks 2026")


def _header(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def run():
    print(f"Topic: {TOPIC!r}\n")
    all_passed = True

    _header("ArXiv Search")
    arxiv_results = fetch_arxiv(TOPIC, max_results=3)
    print(json.dumps(arxiv_results, indent=2))
    if arxiv_results:
        print(f"\n✓ ArXiv: {len(arxiv_results)} results")
    else:
        print("\n✗ ArXiv: returned empty list")
        all_passed = False

    _header("Web Search (Brave)")
    web_results = web_search(TOPIC, num_results=5)
    print(json.dumps(web_results, indent=2))
    if web_results:
        print(f"\n✓ Web: {len(web_results)} results")
    elif not os.environ.get("BRAVE_API_KEY"):
        print("\n~ Web: skipped (BRAVE_API_KEY not set)")
    else:
        print("\n✗ Web: returned empty list")
        all_passed = False

    _header("GitHub Search")
    gh_results = github_search(TOPIC, max_results=5)
    print(json.dumps(gh_results, indent=2))
    if gh_results:
        print(f"\n✓ GitHub: {len(gh_results)} results")
    else:
        print("\n✗ GitHub: returned empty list")
        all_passed = False

    print(f"\n{'='*60}")
    if all_passed:
        print("ALL TOOLS RETURNED NON-EMPTY RESULTS — ready for Phase 3")
    else:
        print("SOME TOOLS RETURNED EMPTY — check API keys in .env")
    print("="*60)
    return all_passed


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
