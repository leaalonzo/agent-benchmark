#!/usr/bin/env python3
"""CLI bridge: openclaw exec -> tools/arxiv_search.fetch_arxiv"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.arxiv_search import fetch_arxiv

topic = sys.argv[1] if len(sys.argv) > 1 else ""
max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 10

print(json.dumps(fetch_arxiv(topic, max_results), ensure_ascii=False))
