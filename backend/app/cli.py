"""Command-line entry points.

Useful for first-boot seeding, for re-running ingest without the API, and for
exercising the pull pipeline on a ticker from a terminal.

    python -m app.cli seed
    python -m app.cli ingest --fundamentals
    python -m app.cli research POLYCAB
    python -m app.cli usage
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.logging import configure_logging, get_logger
from app.db.session import init_db, session_scope

log = get_logger(__name__)


def cmd_seed(_: argparse.Namespace) -> int:
    from app.services.ingest.runner import ensure_companies, get_rule

    init_db()
    with session_scope() as session:
        created = ensure_companies(session)
        get_rule(session)
    print(f"Tracked universe ready. {created} companies created.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from app.services.ingest.runner import run_ingest

    init_db()
    summary = asyncio.run(run_ingest(discover_fundamentals=args.fundamentals))
    print(json.dumps(summary.__dict__, indent=2, default=str))
    return 1 if summary.errors else 0


def cmd_research(args: argparse.Namespace) -> int:
    from app.services.analysis import guidance as guidance_service
    from app.services.analysis import research as research_service

    init_db()

    async def run() -> dict:
        with session_scope() as session:
            company = await research_service.resolve_company(session, args.ticker)
            bundle = await research_service.build_bundle(session, company)
            report = await guidance_service.build_report(
                session, company, quarters=args.quarters
            )
            return {
                "symbol": company.symbol,
                "snapshot": bundle.snapshot,
                "bull_bear": bundle.bull_bear,
                "warnings": bundle.warnings,
                "quarters_covered": report.quarters_covered,
                "scorecard": report.scorecard,
                "note": report.note,
                "claims": [
                    {
                        "said_in": f"Q{r.claim.said_q} FY{str(r.claim.said_fy)[-2:]}",
                        "metric": r.claim.metric,
                        "quote": r.claim.quote,
                        "status": r.outcome.status if r.outcome else None,
                        "reasoning": r.outcome.reasoning if r.outcome else None,
                    }
                    for r in report.records
                ],
            }

    print(json.dumps(asyncio.run(run()), indent=2, default=str))
    return 0


def cmd_usage(_: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.db.models import LLMUsage

    init_db()
    with session_scope() as session:
        rows = list(session.scalars(select(LLMUsage)))
    if not rows:
        print("No model calls recorded yet.")
        return 0

    by_stage: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = by_stage.setdefault(row.stage, {"calls": 0, "cached": 0, "tokens": 0})
        entry["calls"] += 1
        entry["cached"] += int(row.cached)
        entry["tokens"] += row.input_tokens + row.output_tokens

    total = sum(e["tokens"] for e in by_stage.values())
    cached = sum(e["cached"] for e in by_stage.values())
    for stage, entry in sorted(by_stage.items(), key=lambda kv: kv[1]["tokens"], reverse=True):
        print(f"{stage:<32} {entry['calls']:>4} calls  {entry['tokens']:>9,} tokens")
    print(f"{'TOTAL':<32} {len(rows):>4} calls  {total:>9,} tokens  "
          f"({cached}/{len(rows)} served from cache)")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="finn")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Create the tracked universe and default alert rule"
                   ).set_defaults(func=cmd_seed)

    ingest = sub.add_parser("ingest", help="Run the full pipeline once")
    ingest.add_argument("--fundamentals", action="store_true",
                        help="Also discover annual reports and transcripts (slow)")
    ingest.set_defaults(func=cmd_ingest)

    research = sub.add_parser("research", help="Run the pull pipeline on one ticker")
    research.add_argument("ticker")
    research.add_argument("--quarters", type=int, default=4)
    research.set_defaults(func=cmd_research)

    sub.add_parser("usage", help="Show token accounting").set_defaults(func=cmd_usage)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
