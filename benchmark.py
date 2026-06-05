"""
Benchmark orchestrator — runs the same multi-source briefing task through
OpenClaw and Hermes Agent and writes results/ JSON trace logs.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import TypedDict

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
# Trace schema (5.1)
# ---------------------------------------------------------------------------

class ToolCallEntry(TypedDict):
    sequence: int
    tool_name: str
    args: dict
    result_summary: str
    result_count: int
    timestamp: str
    duration_ms: int | None


class OutputSection(TypedDict):
    papers: list
    repos: list
    web: list
    synthesis: str


class TraceSchema(TypedDict):
    agent: str
    topic: str
    status: str
    start_time: str
    end_time: str
    wall_clock_seconds: float
    total_input_tokens: int
    total_output_tokens: int
    tool_calls: list[ToolCallEntry]
    tool_call_count: int
    output: OutputSection
    raw_response: str


# ---------------------------------------------------------------------------
# Prompt template
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
# Response parser
# ---------------------------------------------------------------------------

def _extract_section(text: str, header: str) -> str:
    """Return the text of a named section (case-insensitive)."""
    pattern = rf"(?:^|\n)(?:#+\s*|[*_]{{1,2}})?{re.escape(header)}[*_]{{0,2}}[:\s]*\n(.*?)(?=\n(?:#+\s*|[*_]{{1,2}})?(?:PAPERS|REPOS|WEB|SYNTHESIS)[*_]{{0,2}}[:\s]*\n|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _count_list_items(section_text: str) -> list[str]:
    """Return non-empty lines that look like list items."""
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        if re.match(r"^(\d+[.)]\s|\*\s|-\s|•\s)", line) and len(line) > 5:
            items.append(line)
    return items


def parse_response(text: str) -> OutputSection:
    papers_text = _extract_section(text, "PAPERS")
    repos_text = _extract_section(text, "REPOS")
    web_text = _extract_section(text, "WEB")
    synthesis_text = _extract_section(text, "SYNTHESIS")
    return OutputSection(
        papers=_count_list_items(papers_text),
        repos=_count_list_items(repos_text),
        web=_count_list_items(web_text),
        synthesis=synthesis_text,
    )


# ---------------------------------------------------------------------------
# Trace normaliser
# ---------------------------------------------------------------------------

def _tool_entry(raw: dict, seq: int) -> ToolCallEntry:
    result = raw.get("result") or ""
    if isinstance(result, (list, dict)):
        result_str = json.dumps(result, ensure_ascii=False)
        result_count = len(result) if isinstance(result, list) else 1
    else:
        result_str = str(result)
        try:
            parsed = json.loads(result_str)
            result_count = len(parsed) if isinstance(parsed, list) else 1
        except (json.JSONDecodeError, TypeError):
            result_count = 1 if result_str.strip() else 0

    dur_s = raw.get("duration_seconds")
    return ToolCallEntry(
        sequence=seq,
        tool_name=raw.get("name", ""),
        args=raw.get("args", {}),
        result_summary=result_str[:200],
        result_count=result_count,
        timestamp=raw.get("timestamp", ""),
        duration_ms=round(dur_s * 1000) if dur_s is not None else None,
    )


def normalize_trace(raw: dict, topic: str) -> TraceSchema:
    tokens = raw.get("tokens", {})
    raw_response = raw.get("final_response", "")
    tool_calls = [_tool_entry(tc, i + 1) for i, tc in enumerate(raw.get("tool_calls", []))]
    return TraceSchema(
        agent=raw.get("agent", ""),
        topic=topic,
        status=raw.get("status", "error"),
        start_time=raw.get("start_time", ""),
        end_time=raw.get("end_time", ""),
        wall_clock_seconds=raw.get("duration_seconds", 0.0),
        total_input_tokens=tokens.get("input", 0),
        total_output_tokens=tokens.get("output", 0),
        tool_calls=tool_calls,
        tool_call_count=len(tool_calls),
        output=parse_response(raw_response),
        raw_response=raw_response,
    )


# ---------------------------------------------------------------------------
# Comparison summary printer
# ---------------------------------------------------------------------------

def _fmt(val, width=10) -> str:
    return str(val).ljust(width)


def print_summary(topic: str, oc: TraceSchema, h: TraceSchema) -> None:
    w = 12
    print()
    print("── Benchmark Complete " + "─" * 27)
    print(f"  Topic:              {topic}")
    print()
    print(f"  {'':20s}{'OpenClaw':<{w}}{'Hermes':<{w}}")
    print(f"  {'Tool calls:':<20}{_fmt(oc['tool_call_count'], w)}{_fmt(h['tool_call_count'], w)}")
    print(f"  {'Input tokens:':<20}{_fmt(oc['total_input_tokens'], w)}{_fmt(h['total_input_tokens'], w)}")
    print(f"  {'Wall clock (s):':<20}{_fmt(round(oc['wall_clock_seconds'], 1), w)}{_fmt(round(h['wall_clock_seconds'], 1), w)}")
    print(f"  {'Papers found:':<20}{_fmt(len(oc['output']['papers']), w)}{_fmt(len(h['output']['papers']), w)}")
    print(f"  {'Repos found:':<20}{_fmt(len(oc['output']['repos']), w)}{_fmt(len(h['output']['repos']), w)}")
    print(f"  {'Web results:':<20}{_fmt(len(oc['output']['web']), w)}{_fmt(len(h['output']['web']), w)}")
    print(f"  {'Status:':<20}{_fmt(oc['status'], w)}{_fmt(h['status'], w)}")
    print("  " + "─" * 46)
    print("  Full traces saved to results/")
    print()


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

    oc_trace = h_trace = None

    if run_openclaw:
        logger.info("--- Running OpenClaw ---")
        from runners.openclaw_runner import run_openclaw_session
        raw = run_openclaw_session(topic, prompt)
        oc_trace = normalize_trace(raw, topic)
        (results_dir / "openclaw_trace.json").write_text(
            json.dumps(oc_trace, indent=2, ensure_ascii=False)
        )
        logger.info(
            "OpenClaw: status=%s  tool_calls=%d  tokens=%d/%d  duration=%.1fs",
            oc_trace["status"], oc_trace["tool_call_count"],
            oc_trace["total_input_tokens"], oc_trace["total_output_tokens"],
            oc_trace["wall_clock_seconds"],
        )

    if run_hermes:
        logger.info("--- Running Hermes Agent ---")
        from runners.hermes_runner import run_hermes_session
        raw = run_hermes_session(topic, prompt)
        h_trace = normalize_trace(raw, topic)
        (results_dir / "hermes_trace.json").write_text(
            json.dumps(h_trace, indent=2, ensure_ascii=False)
        )
        logger.info(
            "Hermes: status=%s  tool_calls=%d  tokens=%d/%d  duration=%.1fs",
            h_trace["status"], h_trace["tool_call_count"],
            h_trace["total_input_tokens"], h_trace["total_output_tokens"],
            h_trace["wall_clock_seconds"],
        )

    if oc_trace and h_trace:
        print_summary(topic, oc_trace, h_trace)
    elif oc_trace:
        logger.info("Results written to %s/", results_dir)
    elif h_trace:
        logger.info("Results written to %s/", results_dir)


if __name__ == "__main__":
    topic = os.environ.get("BENCHMARK_TOPIC", "AI agent frameworks 2026")
    only = sys.argv[1] if len(sys.argv) > 1 else "both"
    run_benchmark(
        topic,
        run_openclaw=(only in ("both", "openclaw")),
        run_hermes=(only in ("both", "hermes")),
    )
