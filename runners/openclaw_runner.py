"""
OpenClaw (Claude Code headless) benchmark runner.

Connects to the OpenClaw WebSocket gateway, submits a benchmark prompt,
captures the full tool-call trace, and returns a structured result dict.

Protocol reference: https://docs.openclaw.ai/gateway/protocol
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import websockets
import websockets.exceptions

GATEWAY_URL = "ws://127.0.0.1:18789"
TIMEOUT_SECONDS = 120
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------

def _req(method: str, params: dict) -> str:
    return json.dumps({"type": "req", "id": str(uuid.uuid4()), "method": method, "params": params})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Async core
# ---------------------------------------------------------------------------

async def _run_async(topic: str, prompt: str) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "agent": "openclaw",
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
        async with websockets.connect(GATEWAY_URL, open_timeout=10) as ws:

            # --- handshake -------------------------------------------------
            await ws.send(_req("connect", {
                "minProtocol": 3,
                "maxProtocol": 4,
                "client": {"id": "benchmark", "version": "1.0.0", "platform": "linux", "mode": "operator"},
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
            }))
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if not hello.get("ok"):
                trace["status"] = "error"
                trace["error"] = f"handshake failed: {hello}"
                return _finalise(trace, wall_start)

            # --- create session --------------------------------------------
            session_id = str(uuid.uuid4())
            await ws.send(_req("session.create", {
                "id": session_id,
                "model": os.environ.get("MODEL", "gpt-4o"),
                "prompt": prompt,
            }))

            # --- event loop -----------------------------------------------
            tool_call_buffer: dict[str, dict] = {}   # call_id -> in-flight tool call

            async def recv_loop():
                async for raw in ws:
                    event = json.loads(raw)
                    trace["raw_events"].append(event)
                    etype = event.get("event", event.get("type", ""))

                    # --- tool call started ---------------------------------
                    if etype == "session.tool":
                        payload = event.get("payload", {})
                        tool_type = payload.get("type")

                        if tool_type == "tool_use":
                            call_id = payload.get("id", str(uuid.uuid4()))
                            tool_call_buffer[call_id] = {
                                "name": payload.get("name", ""),
                                "args": payload.get("input", {}),
                                "result": None,
                                "timestamp": _now(),
                                "call_start": time.monotonic(),
                                "duration_seconds": None,
                            }

                        elif tool_type == "tool_result":
                            call_id = payload.get("tool_use_id", "")
                            if call_id in tool_call_buffer:
                                entry = tool_call_buffer.pop(call_id)
                                entry["result"] = payload.get("content")
                                entry["duration_seconds"] = round(
                                    time.monotonic() - entry.pop("call_start"), 3
                                )
                                trace["tool_calls"].append(entry)
                            else:
                                trace["tool_calls"].append({
                                    "name": "unknown",
                                    "args": {},
                                    "result": payload.get("content"),
                                    "timestamp": _now(),
                                    "duration_seconds": None,
                                })

                    # --- token / response metadata ------------------------
                    elif etype == "session.message":
                        payload = event.get("payload", {})
                        usage = payload.get("usage") or {}
                        if usage:
                            trace["tokens"]["input"] += usage.get("input_tokens", 0)
                            trace["tokens"]["output"] += usage.get("output_tokens", 0)
                        # capture final text content
                        for block in payload.get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                trace["final_response"] = block.get("text", "")

                    # --- session done -------------------------------------
                    elif etype in ("session.complete", "session.stop", "session.done"):
                        payload = event.get("payload", {})
                        trace["status"] = payload.get("status", "complete")
                        return

                    # --- errors -------------------------------------------
                    elif etype == "session.error":
                        trace["status"] = "error"
                        trace["error"] = event.get("payload", {}).get("message", "unknown error")
                        return

            try:
                await asyncio.wait_for(recv_loop(), timeout=TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                trace["status"] = "timeout"
                logger.warning("OpenClaw session timed out after %ss", TIMEOUT_SECONDS)

    except (ConnectionRefusedError, OSError) as exc:
        trace["status"] = "error"
        trace["error"] = f"cannot connect to OpenClaw gateway at {GATEWAY_URL}: {exc}"
        logger.error(trace["error"])
    except websockets.exceptions.WebSocketException as exc:
        trace["status"] = "error"
        trace["error"] = f"WebSocket error: {exc}"
        logger.error(trace["error"])

    return _finalise(trace, wall_start)


def _finalise(trace: dict, wall_start: float) -> dict:
    trace["end_time"] = _now()
    trace["duration_seconds"] = round(time.monotonic() - wall_start, 3)
    return trace


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_openclaw_session(topic: str, prompt: str) -> dict[str, Any]:
    """Run a single OpenClaw benchmark session and return the trace dict."""
    return asyncio.run(_run_async(topic, prompt))
