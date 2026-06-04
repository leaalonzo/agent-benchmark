"""
OpenClaw benchmark runner.

Connects to the OpenClaw WebSocket gateway (installed directly on the VPS),
submits a benchmark prompt, captures the full tool-call trace, and returns
a structured result dict.

Protocol reference: https://docs.openclaw.ai/gateway/protocol
"""

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets
import websockets.exceptions
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

GATEWAY_URL = "ws://127.0.0.1:18789"
TIMEOUT_SECONDS = 120
DEVICE_JSON = Path.home() / ".openclaw" / "identity" / "device.json"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Device identity helpers
# ---------------------------------------------------------------------------

def _load_device() -> dict:
    """Read device id and private key from OpenClaw's local identity file."""
    with open(DEVICE_JSON) as f:
        return json.load(f)


def _load_gateway_token() -> str:
    """Read the shared gateway auth token from openclaw.json."""
    with open(OPENCLAW_CONFIG) as f:
        config = json.load(f)
    return config.get("gateway", {}).get("auth", {}).get("token", "")


def _sign(private_key_pem: str, payload: str) -> str:
    """Sign a payload string with the Ed25519 private key; return base64."""
    key: Ed25519PrivateKey = load_pem_private_key(private_key_pem.encode(), password=None)
    sig = key.sign(payload.encode())
    return base64.b64encode(sig).decode()


def _sig_payload(device_id: str, nonce: str, signed_at: int, scopes: list[str], token: str) -> str:
    """Build the v2 pipe-delimited signing payload for the connect request."""
    return f"v2|{device_id}|cli|cli|operator|{','.join(scopes)}|{signed_at}|{token}|{nonce}"


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
        device = _load_device()
        gateway_token = _load_gateway_token()
    except FileNotFoundError as exc:
        trace["error"] = f"config file not found: {exc}"
        return _finalise(trace, wall_start)

    try:
        async with websockets.connect(GATEWAY_URL, open_timeout=10) as ws:

            # --- wait for gateway challenge ---------------------------------
            # Gateway sends connect.challenge first; client signs the server
            # nonce and echoes it back in the connect request.
            challenge = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if challenge.get("event") != "connect.challenge":
                trace["status"] = "error"
                trace["error"] = f"expected connect.challenge, got: {challenge}"
                return _finalise(trace, wall_start)

            server_nonce = challenge["payload"]["nonce"]
            signed_at = challenge["payload"]["ts"]
            scopes = ["operator.read", "operator.write"]
            device_sig = _sign(
                device["privateKeyPem"],
                _sig_payload(device["deviceId"], server_nonce, signed_at, scopes, gateway_token),
            )

            # --- send connect -----------------------------------------------
            await ws.send(_req("connect", {
                "minProtocol": 3,
                "maxProtocol": 4,
                "client": {
                    "id": "cli",
                    "version": "1.0.0",
                    "platform": "linux",
                    "mode": "cli",
                },
                "role": "operator",
                "scopes": scopes,
                "auth": {"token": gateway_token},
                "device": {
                    "id": device["deviceId"],
                    "publicKey": device["publicKeyPem"],
                    "signature": device_sig,
                    "signedAt": signed_at,
                    "nonce": server_nonce,
                },
            }))

            # --- await success ----------------------------------------------
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if not msg.get("ok"):
                trace["status"] = "error"
                trace["error"] = f"handshake failed: {msg}"
                return _finalise(trace, wall_start)

            # --- create session --------------------------------------------
            session_id = str(uuid.uuid4())
            await ws.send(_req("session.create", {
                "id": session_id,
                "model": os.environ.get("MODEL", "gpt-4o"),
                "prompt": prompt,
            }))

            # --- event loop -----------------------------------------------
            tool_call_buffer: dict[str, dict] = {}

            async def recv_loop():
                async for raw in ws:
                    event = json.loads(raw)
                    trace["raw_events"].append(event)
                    etype = event.get("event", event.get("type", ""))

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

                    elif etype == "session.message":
                        payload = event.get("payload", {})
                        usage = payload.get("usage") or {}
                        if usage:
                            trace["tokens"]["input"] += usage.get("input_tokens", 0)
                            trace["tokens"]["output"] += usage.get("output_tokens", 0)
                        for block in payload.get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                trace["final_response"] = block.get("text", "")

                    elif etype in ("session.complete", "session.stop", "session.done"):
                        trace["status"] = event.get("payload", {}).get("status", "complete")
                        return

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
