#!/usr/bin/env python3
"""Per-cell medians of a session: every recorded run of a cell (5 rounds x N runs), plus the plain round's median.

usage: python3 tools/summary.py results/<session>      writes results/<session>/summary.json
"""

import json
import statistics
import sys
from pathlib import Path


def summarize(rows: list[dict]) -> dict:
    cells = {}
    for name in dict.fromkeys(r["cell"] for r in rows):
        recorded = [t for r in rows if r["cell"] == name and r["round"] != "plain" for t in r["runs_s"]]
        plain = [t for r in rows if r["cell"] == name and r["round"] == "plain" for t in r["runs_s"]]
        first = next(r for r in rows if r["cell"] == name)
        cells[name] = {
            "test": first["test"],
            "label": first["label"],
            "runs": len(recorded),
            "median_s": round(statistics.median(recorded), 4),
            "min_s": round(min(recorded), 4),
            "max_s": round(max(recorded), 4),
            "plain_median_s": round(statistics.median(plain), 4) if plain else None,
        }
    return cells


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    session = Path(sys.argv[1])
    rows = [json.loads(line) for line in (session / "runs.jsonl").read_text().splitlines() if line.strip()]
    if not rows:
        sys.exit(f"{session}: no runs")
    out = session / "summary.json"
    out.write_text(json.dumps(summarize(rows), indent=2) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
