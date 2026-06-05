"""
Hermes Agent benchmark runner.

Runs a benchmark prompt through Hermes Agent CLI (`hermes -z`), then
exports the last session to extract tool call traces.

Prerequisites (run on VPS):
  hermes mcp add benchmark-tools --command "python3 /root/agent-benchmark/tools/mcp_server.py"
  hermes config set model gpt-5.5
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


def _export_session(run_start_ts: float) -> tuple[list[dict], dict]:
    """Export Hermes sessions, find the one matching this run, return (tool_calls, tokens)."""
    import os, tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    try:
        result = subprocess.run(
            [HERMES_CMD, "sessions", "export", tmp.name],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("hermes sessions export failed: %s", result.stderr[:200])
            return [], {}
        with open(tmp.name) as f:
            lines = f.readlines()
    except Exception as exc:
        logger.warning("Could not export session: %s", exc)
        return [], {}
    finally:
        os.unlink(tmp.name)

    # Find the most recently started session
    sessions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            sessions.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not sessions:
        return [], {}

    best = max(sessions, key=lambda s: s.get("started_at", ""))

    tokens = {
        "input": best.get("input_tokens", 0) or 0,
        "output": best.get("output_tokens", 0) or 0,
    }

    # Parse tool calls from messages
    tool_calls: list[dict] = []
    messages = best.get("messages", [])
    tool_result_map: dict[str, str] = {}

    for msg in messages:
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            call_id = msg.get("tool_call_id", "")
            if call_id:
                tool_result_map[call_id] = content

    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            call_id = tc.get("id", tc.get("call_id", ""))
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "name": fn.get("name", ""),
                "args": args,
                "result": tool_result_map.get(call_id),
                "timestamp": _now(),
                "duration_seconds": None,
            })

    return tool_calls, tokens




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
        tool_calls, tokens = _export_session(wall_start)
        trace["tool_calls"] = tool_calls
        trace["tokens"] = tokens

    except subprocess.TimeoutExpired:
        logger.warning("Hermes session timed out after %ss", TIMEOUT_SECONDS)
        trace["status"] = "timeout"
        tool_calls, tokens = _export_session(wall_start)
        trace["tool_calls"] = tool_calls
        trace["tokens"] = tokens

    except FileNotFoundError:
        trace["error"] = f"hermes command not found — is Hermes Agent installed? (looked for: {HERMES_CMD})"
        logger.error(trace["error"])

    except RuntimeError as exc:
        trace["error"] = str(exc)
        logger.error("Hermes error: %s", exc)

    trace["end_time"] = _now()
    trace["duration_seconds"] = round(time.monotonic() - wall_start, 3)
    return trace
