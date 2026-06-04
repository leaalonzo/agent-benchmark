"""
Benchmark orchestrator — runs the same multi-source briefing task through
OpenClaw and Hermes Agent and writes results/ JSON trace logs.
"""

import json
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
_env = Path(__file__).parent / ".env"
if _env.exists():
    with open(_env) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Prompt template  (3.4)
# ---------------------------------------------------------------------------

BENCHMARK_PROMPT_TEMPLATE = """\
You are a research assistant. Using the tools available to you, produce a structured briefing on the following topic:

TOPIC: {topic}

Your briefing must include:
1. PAPERS: 3-5 relevant recent papers from ArXiv with title, one-sentence summary, and link
2. REPOS: 3 relevant GitHub repositories with name, stars, and one-line description
3. WEB: 2-3 relevant recent articles or posts with title, source, and one-sentence summary
4. SYNTHESIS: A 2-3 paragraph summary of what is currently happening in this area

Use each tool at least once. Do not fabricate results — only include what the tools return.
"""


def build_prompt(topic: str) -> str:
    return BENCHMARK_PROMPT_TEMPLATE.format(topic=topic)


# ---------------------------------------------------------------------------
# Trace schema helper
# ---------------------------------------------------------------------------

def empty_trace(agent: str, topic: str) -> dict:
    """Return a trace skeleton matching the expected schema."""
    return {
        "agent": agent,
        "topic": topic,
        "status": "not_run",
        "start_time": None,
        "end_time": None,
        "duration_seconds": None,
        "tool_calls": [],          # list of {name, args, result, timestamp, duration_seconds}
        "tokens": {"input": 0, "output": 0},
        "final_response": "",
        "raw_events": [],
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")


def run_benchmark(topic: str, run_openclaw: bool = True, run_hermes: bool = True) -> None:
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    prompt = build_prompt(topic)
    logger.info("Topic: %r", topic)
    logger.info("Prompt length: %d chars", len(prompt))

    if run_openclaw:
        logger.info("--- Running OpenClaw ---")
        from runners.openclaw_runner import run_openclaw_session
        oc_trace = run_openclaw_session(topic, prompt)
        out = results_dir / "openclaw_trace.json"
        out.write_text(json.dumps(oc_trace, indent=2, ensure_ascii=False))
        logger.info(
            "OpenClaw: status=%s  tool_calls=%d  tokens=%s  duration=%.1fs",
            oc_trace["status"],
            len(oc_trace["tool_calls"]),
            oc_trace["tokens"],
            oc_trace.get("duration_seconds") or 0,
        )

    if run_hermes:
        logger.info("--- Running Hermes Agent ---")
        from runners.hermes_runner import run_hermes_session
        h_trace = run_hermes_session(topic, prompt)
        out = results_dir / "hermes_trace.json"
        out.write_text(json.dumps(h_trace, indent=2, ensure_ascii=False))
        logger.info(
            "Hermes: status=%s  tool_calls=%d  tokens=%s  duration=%.1fs",
            h_trace["status"],
            len(h_trace["tool_calls"]),
            h_trace["tokens"],
            h_trace.get("duration_seconds") or 0,
        )

    logger.info("Results written to %s/", results_dir)


if __name__ == "__main__":
    topic = os.environ.get("BENCHMARK_TOPIC", "AI agent frameworks 2026")
    only = sys.argv[1] if len(sys.argv) > 1 else "both"
    run_benchmark(
        topic,
        run_openclaw=(only in ("both", "openclaw")),
        run_hermes=(only in ("both", "hermes")),
    )
