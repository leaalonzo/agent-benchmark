# Agent Benchmark

A head-to-head benchmark that runs the same multi-source research task through two AI agents — **OpenClaw** and **Hermes Agent** — and compares them on tool usage, token consumption, latency, and output quality. Each agent is asked to produce a structured briefing on a topic using ArXiv, GitHub, and web search tools. Results are saved as JSON traces and visualised in a local Flask dashboard.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | On the VPS and Mac |
| Node.js | 20+ | Required by OpenClaw |
| VPS | Ubuntu 22.04+ | 4 GB RAM minimum; tested on Hetzner 8 GB |
| OpenAI API key | — | Used by both agents (gpt-5.5) |
| Brave Search API key | — | Used by the `web_search` tool |
| GitHub token | — | Optional; increases rate limit for `github_search` |

---

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/leaalonzo/agent-benchmark.git
cd agent-benchmark
cp .env.example .env
# Fill in OPENAI_API_KEY, BRAVE_API_KEY, GITHUB_TOKEN, BENCHMARK_TOPIC
```

### 2. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Install OpenClaw on the VPS

```bash
# Install
curl -fsSL https://openclaw.ai/install.sh | bash

# Start the gateway (keep this running in tab 1)
openclaw

# Register the benchmark MCP tools
hermes mcp add benchmark-tools --command python3 \
  --args "/root/agent-benchmark/tools/mcp_server.py"

# Configure model
# In the OpenClaw TUI: set model to openai/gpt-5.5
# Edit ~/.openclaw/openclaw.json to register the model in models.providers
```

### 4. Install Hermes Agent on the VPS

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup model   # select openai-api, enter key, set gpt-5.5
hermes config set memory.memory_enabled false
```

---

## Running the benchmark

```bash
# Run both agents (takes ~2 minutes)
python3 benchmark.py

# Run a single agent
python3 benchmark.py openclaw
python3 benchmark.py hermes

# Verify results
python3 verify.py

# Launch the dashboard
python3 dashboard/app.py
```

Then on your Mac, open an SSH tunnel and view the dashboard:

```bash
ssh -L 5000:localhost:5000 root@<your-vps-ip>
# Open http://localhost:5000
```

---

## Output

### Terminal summary

After both agents complete, the benchmark prints a comparison table:

```
── Benchmark Complete ───────────────────────────
  Topic:              "AI agent frameworks 2026"

                      OpenClaw    Hermes
  Tool calls:         4           24
  Input tokens:       14876       48406
  Wall clock (s):     38.9        82.9
  Papers found:       5           5
  Repos found:        3           3
  Web results:        3           3
  Status:             complete    complete
  ──────────────────────────────────────────────
  Full traces saved to results/
```

### JSON traces

Two files are written to `results/`:

- `openclaw_trace.json` — full trace including tool call timeline, response, and parsed output sections
- `hermes_trace.json` — same schema for Hermes

Each trace follows this schema:

```json
{
  "agent": "openclaw",
  "topic": "...",
  "status": "complete",
  "wall_clock_seconds": 38.9,
  "total_input_tokens": 14876,
  "total_output_tokens": 1040,
  "tool_call_count": 4,
  "tool_calls": [
    {
      "sequence": 1,
      "tool_name": "web_search",
      "args": { "meta": "for \"AI agent frameworks 2026\"" },
      "duration_ms": 2400,
      "result_count": 0
    }
  ],
  "output": {
    "papers": ["1. Some Paper — summary (arxiv.org/...)"],
    "repos": ["1. org/repo — description"],
    "web": ["1. Article — source — summary"],
    "synthesis": "..."
  },
  "raw_response": "..."
}
```

### Dashboard

The Flask dashboard at `http://localhost:5000` shows:

- **Metrics table** — tool calls, tokens, wall clock, output counts, status side by side
- **Tool call timelines** — each call with sequence number, name, expandable args and result preview, duration
- **Output sections** — Papers, Repos, Web results side by side per agent
- **Synthesis comparison** — both synthesis paragraphs side by side for easy diff

---

## Results

*Benchmark topic: "AI agent frameworks 2026" — run 2026-06-05 on Hetzner VPS (Ubuntu 22.04, 8 GB RAM)*

| Metric | OpenClaw | Hermes |
|--------|---------|--------|
| Status | complete | complete |
| Tool calls | 4 | 24 |
| Input tokens | 14,876 | 48,406 |
| Output tokens | 1,040 | ~3,400 |
| Wall clock | 38.9 s | 82.9 s |
| Papers found | 5 | 5 |
| Repos found | 3 | 3 |
| Web results | 3 | 3 |

---

## Lessons

**OpenClaw is 2× faster and uses 3× fewer tokens for identical output quality.**
Both agents returned 5 papers, 3 repos, and 3 web results — the structured output was equivalent. But OpenClaw reached that result in 4 tool calls versus Hermes's 24.

**OpenClaw uses code to orchestrate; Hermes uses agent scaffolding.**
OpenClaw's Codex plugin wrote and ran a Python script (1 `bash` call) to perform all searches, then used `web_search` for additional results. Hermes spent several turns calling `skill_view` and `skills_list` — introspective meta-calls to understand its own capabilities — before doing any research.

**Hermes uses its own built-in tools, not the registered MCP server.**
Despite registering a custom MCP server with `arxiv_search` and `github_search`, Hermes fell back to its own `web_search` tool for everything. The MCP server connection failed during setup (Hermes reported it couldn't verify the server). In a controlled experiment both agents should use the same tools.

**Token cost scales with tool calls, not output length.**
Hermes used 3.3× more input tokens largely because each of its 24 tool calls added context to the conversation window. The final responses were similar in length.

**OpenClaw token counts require reading trajectory files.**
OpenClaw's WebSocket API does not emit token usage events. Token counts were recovered by reading `~/.openclaw/agents/main/sessions/{sessionId}.trajectory.jsonl` and summing `model.completed` entries after the run.
