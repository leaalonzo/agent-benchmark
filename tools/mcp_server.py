#!/usr/bin/env python3
"""
MCP stdio server exposing arxiv_search, web_search, and github_search.

Register with Hermes:
  hermes mcp add benchmark-tools --command "python3 /root/agent-benchmark/tools/mcp_server.py"
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.arxiv_search import fetch_arxiv
from tools.web_search import web_search
from tools.github_search import github_search

TOOLS = [
    {
        "name": "arxiv_search",
        "description": "Search ArXiv for recent academic papers on a topic. Returns titles, abstracts, authors, and URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 10, "description": "Max papers to return"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web using Brave Search. Returns titles, URLs, and descriptions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "default": 5, "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_search",
        "description": "Search GitHub repositories by topic or keyword. Returns name, stars, description, and URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5, "description": "Max repos to return"},
            },
            "required": ["query"],
        },
    },
]


def _call_tool(name: str, args: dict) -> str:
    if name == "arxiv_search":
        result = fetch_arxiv(args["topic"], args.get("max_results", 10))
    elif name == "web_search":
        result = web_search(args["query"], args.get("num_results", 5))
    elif name == "github_search":
        result = github_search(args["query"], args.get("max_results", 5))
    else:
        raise ValueError(f"Unknown tool: {name}")
    return json.dumps(result, ensure_ascii=False)


def _respond(req_id, result=None, error=None) -> dict:
    frame = {"jsonrpc": "2.0", "id": req_id}
    if error:
        frame["error"] = error
    else:
        frame["result"] = result
    return frame


def handle(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return _respond(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "benchmark-tools", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _respond(req_id, {"tools": TOOLS})

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments", {})
        try:
            text = _call_tool(name, args)
            return _respond(req_id, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:
            return _respond(req_id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})

    return _respond(req_id, error={"code": -32601, "message": f"Unknown method: {method}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
