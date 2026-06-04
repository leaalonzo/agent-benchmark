#!/usr/bin/env python3
"""CLI bridge: openclaw exec -> tools/github_search.github_search"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.github_search import github_search

query = sys.argv[1] if len(sys.argv) > 1 else ""
max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5

print(json.dumps(github_search(query, max_results), ensure_ascii=False))
