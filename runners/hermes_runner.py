"""
Hermes Agent benchmark runner.

Runs a benchmark prompt through Hermes Agent CLI (`hermes -z`), then
exports the last session to extract tool call traces.

Prerequisites (run on VPS):
  hermes mcp add benchmark-tools --command "python3 /root/agent-benchmark/tools/mcp_server.py"
  hermes config set model gpt-4o
  hermes config set memory.memory_enabled false
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

HERMES_CMD = os.environ.get("HERMES_CMD", "hermes")
TIMEOUT_SECONDS = 180
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_prompt(prompt: str) -> str:
    """Run hermes -z and return the response text."""
    result = subprocess.run(
        [HERMES_CMD, "-z", prompt],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"hermes exited {result.returncode}: {result.stderr[:400]}")
    return result.stdout.strip()


def _export_tool_calls() -> list[dict]:
    """Export the last Hermes session and parse tool call entries."""
    try:
        result = subprocess.run(
            [HERMES_CMD, "sessions", "export", "--last"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("hermes sessions export failed: %s", result.stderr[:200])
            return []
    except Exception as exc:
        logger.warning("Could not export session: %s", exc)
        return []

    tool_calls: list[dict] = []
    pending: dict | None = None

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = entry.get("type", entry.get("role", ""))

        if etype in ("tool_use", "tool_call"):
            pending = {
                "name": entry.get("name", entry.get("tool", "")),
                "args": entry.get("input", entry.get("arguments", {})),
                "result": None,
                "timestamp": entry.get("timestamp", _now()),
                "duration_seconds": round(entry.get("duration_ms", 0) / 1000, 3),
            }
            tool_calls.append(pending)

        elif etype in ("tool_result", "tool_response") and pending is not None:
            content = entry.get("content", entry.get("output", ""))
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            pending["result"] = content
            pending = None

    return tool_calls


def run_hermes_session(topic: str, prompt: str) -> dict[str, Any]:
    """Run a single Hermes benchmark session and return the trace dict."""
    trace: dict[str, Any] = {
        "agent": "hermes",
        "topic": topic,
        "status": "error",
        "start_time": _now(),
        "end_time": None,
        "duration_seconds": None,
        "tool_calls": [],
        "tokens": {"input": 0, "output": 0},
        "final_response": "",
        "raw_events": [],
    }
    wall_start = time.monotonic()

    try:
        trace["final_response"] = _run_prompt(prompt)
        trace["status"] = "complete"
        trace["tool_calls"] = _export_tool_calls()

    except subprocess.TimeoutExpired:
        logger.warning("Hermes session timed out after %ss", TIMEOUT_SECONDS)
        trace["status"] = "timeout"
        trace["tool_calls"] = _export_tool_calls()

    except FileNotFoundError:
        trace["error"] = f"hermes command not found — is Hermes Agent installed? (looked for: {HERMES_CMD})"
        logger.error(trace["error"])

    except RuntimeError as exc:
        trace["error"] = str(exc)
        logger.error("Hermes error: %s", exc)

    trace["end_time"] = _now()
    trace["duration_seconds"] = round(time.monotonic() - wall_start, 3)
    return trace
