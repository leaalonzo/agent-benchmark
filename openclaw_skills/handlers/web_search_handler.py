#!/usr/bin/env python3
"""CLI bridge: openclaw exec -> tools/web_search.web_search"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.web_search import web_search

query = sys.argv[1] if len(sys.argv) > 1 else ""
num_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5

print(json.dumps(web_search(query, num_results), ensure_ascii=False))
