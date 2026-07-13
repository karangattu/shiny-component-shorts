#!/usr/bin/env python3
"""Estimate the Claude API list-price cost of a Claude Code session.

Parses the session transcript JSONL (~/.claude/projects/<project-slug>/<session>.jsonl),
dedupes assistant messages by message ID, sums token usage per model, and applies
Anthropic list prices. The result is an ESTIMATE of what the session would cost at
API list prices — subscription (Pro/Max) sessions are not billed this way, and the
authoritative number, when available, is `/cost` in-session or `total_cost_usd`
from `claude -p --output-format json`.

Pricing snapshot (USD per million tokens) checked 2026-07-13 against the
claude-api skill / platform.claude.com pricing page. Cache write assumes the
5-minute TTL (1.25x input); cache read is 0.1x input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PRICING_CHECKED = "2026-07-13"

# model-id prefix -> (input, output) USD per 1M tokens
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-4": (5.0, 25.0),
    # Sonnet 5 intro pricing ($2/$10) applies through 2026-08-31; list is $3/$15.
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (1.0, 5.0),
}
CACHE_WRITE_MULT = 1.25  # 5-minute TTL
CACHE_READ_MULT = 0.10

NOTES = [
    "List-price estimate from transcript token counts; not an invoice.",
    "Usage-billed accounts (Enterprise/API): this approximates the actual charge, "
    "subject to negotiated rates — the Console usage dashboard is authoritative.",
    "Subscription (Pro/Max) sessions are included in the plan; the marginal charge may be $0.",
    "Sonnet 5 priced at intro rates ($2/$10 per MTok) valid through 2026-08-31.",
    "Cache writes priced at the 5-minute-TTL rate (1.25x input).",
]


def price_for(model: str) -> tuple[float, float] | None:
    for prefix, prices in PRICES.items():
        if model.startswith(prefix):
            return prices
    return None


def find_transcript(project_dir: Path, session: str | None) -> Path:
    if session:
        path = project_dir / f"{session}.jsonl"
        if not path.is_file():
            sys.exit(f"No transcript found: {path}")
        return path
    candidates = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        sys.exit(f"No transcripts in {project_dir}")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Estimate the Claude API list-price cost of a Claude Code session."
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
        help="Transcript dir, e.g. ~/.claude/projects/<project-slug>",
    )
    parser.add_argument("--session", help="Session UUID (default: most recent transcript)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    args = parser.parse_args()

    transcript = find_transcript(args.project_dir.expanduser(), args.session)

    # Dedupe by message id: transcripts can carry several records per assistant
    # message (progressive writes); the last one has the final usage.
    by_id: dict[str, dict] = {}
    with transcript.open() as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            model = msg.get("model")
            if not usage or not model or model == "<synthetic>":
                continue
            by_id[msg.get("id") or rec.get("uuid", "")] = {"model": model, "usage": usage}

    totals: dict[str, dict[str, int]] = {}
    for entry in by_id.values():
        u = entry["usage"]
        t = totals.setdefault(
            entry["model"], {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
        )
        t["input"] += u.get("input_tokens", 0) or 0
        t["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
        t["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        t["output"] += u.get("output_tokens", 0) or 0

    rows = []
    grand_total = 0.0
    unpriced = []
    for model, t in sorted(totals.items()):
        prices = price_for(model)
        if prices is None:
            unpriced.append(model)
            continue
        inp, out = prices
        cost = (
            t["input"] * inp
            + t["cache_write"] * inp * CACHE_WRITE_MULT
            + t["cache_read"] * inp * CACHE_READ_MULT
            + t["output"] * out
        ) / 1_000_000
        grand_total += cost
        rows.append({"model": model, **t, "estimated_cost_usd": round(cost, 4)})

    report = {
        "transcript": str(transcript),
        "session": transcript.stem,
        "pricing_checked": PRICING_CHECKED,
        "currency": "USD",
        "models": rows,
        "unpriced_models": unpriced,
        "estimated_list_price_total_usd": round(grand_total, 4),
        "notes": NOTES,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"Claude session cost estimate — {transcript.stem}")
    print(f"Pricing checked {PRICING_CHECKED} (USD, list prices)\n")
    print("| Model | Input | Cache write | Cache read | Output | Est. cost |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for r in rows:
        print(
            f"| {r['model']} | {r['input']:,} | {r['cache_write']:,} "
            f"| {r['cache_read']:,} | {r['output']:,} | ${r['estimated_cost_usd']:.4f} |"
        )
    print(f"\nEstimated list-price total: ${grand_total:.4f}")
    if unpriced:
        print(f"Unpriced models (add to PRICES): {', '.join(unpriced)}")
    for note in NOTES:
        print(f"- {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
