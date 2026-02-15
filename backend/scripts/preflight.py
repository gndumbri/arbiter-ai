"""CLI preflight checks for sandbox/production readiness."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from app.core.preflight import run_preflight


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Arbiter backend preflight checks and return a CI-friendly exit code.",
    )
    parser.add_argument(
        "--expected-mode",
        choices=("sandbox", "production"),
        default=None,
        help="Fail if APP_MODE does not match this value.",
    )
    parser.add_argument(
        "--probe-embedding",
        action="store_true",
        help="Run a live embedder call (cost-incurring for hosted providers).",
    )
    parser.add_argument(
        "--probe-llm",
        action="store_true",
        help="Run a live LLM completion call (cost-incurring for hosted providers).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print report as JSON instead of human-readable text.",
    )
    return parser


def _render_text_report(report: dict) -> str:
    lines = []
    status = "PASSED" if report["ok"] else "FAILED"
    lines.append(f"Preflight {status} (mode={report['mode']}, timestamp={report['timestamp_utc']})")
    for check in report["checks"]:
        icon = "OK" if check["ok"] else "FAIL"
        lines.append(f"[{icon}] {check['name']}: {check['detail']}")
    return "\n".join(lines)


async def _run(args: argparse.Namespace) -> int:
    report = await run_preflight(
        expected_mode=args.expected_mode,
        probe_embedding=args.probe_embedding,
        probe_llm=args.probe_llm,
    )
    payload = report.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text_report(payload))
    return 0 if report.ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
