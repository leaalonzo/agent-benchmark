"""Benchmark comparison dashboard — single-route Flask app."""

import json
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

RESULTS = Path(__file__).parent.parent / "results"


def _load(name: str) -> dict | None:
    path = RESULTS / f"{name}_trace.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


@app.route("/")
def index():
    oc = _load("openclaw")
    h = _load("hermes")
    return render_template("index.html", openclaw=oc, hermes=h)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
