"""
Verification script — loads both trace files and asserts correctness.
Prints PASS or lists every failing check.
"""

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
PLACEHOLDER_PHRASES = {"not yet run", "placeholder", "n/a", "none", "todo"}


def load(name: str) -> dict:
    path = RESULTS / f"{name}_trace.json"
    if not path.exists():
        fail(f"{path.name} not found — run benchmark.py first")
    return json.loads(path.read_text())


failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(f"  FAIL  {message}")


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def verify_trace(trace: dict, agent: str) -> None:
    check(trace["status"] == "complete",
          f"[{agent}] status is '{trace['status']}', expected 'complete'")

    check(trace["tool_call_count"] >= 3,
          f"[{agent}] only {trace['tool_call_count']} tool call(s), expected >= 3")

    out = trace.get("output", {})
    for key in ("papers", "repos", "web"):
        items = out.get(key, [])
        check(len(items) > 0,
              f"[{agent}] output.{key} is empty")

    synthesis = out.get("synthesis", "").strip()
    check(len(synthesis) > 20,
          f"[{agent}] synthesis is too short ({len(synthesis)} chars)")
    check(synthesis.lower() not in PLACEHOLDER_PHRASES,
          f"[{agent}] synthesis looks like a placeholder: {synthesis[:60]!r}")

    wall = trace.get("wall_clock_seconds", 0)
    check(wall > 2,
          f"[{agent}] wall_clock_seconds={wall:.1f} is implausibly fast (< 2s)")
    check(wall < 300,
          f"[{agent}] wall_clock_seconds={wall:.1f} exceeds 300s limit")


oc = load("openclaw")
h  = load("hermes")

verify_trace(oc, "openclaw")
verify_trace(h, "hermes")

oc_tok = oc.get("total_input_tokens", 0)
h_tok  = h.get("total_input_tokens", 0)
check(oc_tok > 0 or h_tok > 0,
      "total_input_tokens is 0 for both agents — at least one must be > 0")

if failures:
    print("── Verification FAILED ──────────────────────────")
    for f in failures:
        print(f)
    print(f"\n{len(failures)} check(s) failed.")
    sys.exit(1)
else:
    print("── Verification PASSED ──────────────────────────")
    print(f"  openclaw  status={oc['status']}  tools={oc['tool_call_count']}  wall={oc['wall_clock_seconds']:.1f}s")
    print(f"  hermes    status={h['status']}   tools={h['tool_call_count']}  wall={h['wall_clock_seconds']:.1f}s")
    print(f"  input tokens: openclaw={oc_tok}  hermes={h_tok}")
    print("─────────────────────────────────────────────────")
    print("PASS")
