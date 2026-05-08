"""CLI 진입점 — argparse 만. 비즈니스 로직은 main.py."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date


@dataclass
class CliArgs:
    ticker: str
    peers: list[str] | None
    report_date: date
    skip_llm: bool


def _parse_peers(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    items = [p.strip() for p in raw.split(",")]
    items = [p for p in items if p]
    if not items:
        return None
    for p in items:
        if not (p.isdigit() and len(p) == 6):
            raise argparse.ArgumentTypeError(
                f"피어 코드는 6자리 숫자여야 합니다: {p}"
            )
    return items


def _parse_date(raw: str | None) -> date:
    if raw is None:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError(
            f"--date 는 YYYY-MM-DD 형식이어야 합니다: {raw}"
        ) from exc


def parse_args(argv: list[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        prog="report-stock",
        description="KRX 종목 일일 분석 리포트 생성 (결정론 코어, Phase 1)",
    )
    parser.add_argument(
        "ticker",
        help="6자리 KRX 종목코드 (예: 329180, 005930)",
    )
    parser.add_argument(
        "--peers",
        type=str,
        default=None,
        help="콤마 구분 피어 코드 (생략 시 섹터 기반 자동 선정)",
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=str,
        default=None,
        help="리포트 발행 기준일 (YYYY-MM-DD, 생략 시 오늘)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="LLM 코멘트 스킵 (Phase 1 기본 동작. Phase 2 진입 후 의미 가짐)",
    )

    ns = parser.parse_args(argv)
    if not (ns.ticker.isdigit() and len(ns.ticker) == 6):
        parser.error(f"ticker 는 6자리 숫자여야 합니다: {ns.ticker}")

    return CliArgs(
        ticker=ns.ticker,
        peers=_parse_peers(ns.peers),
        report_date=_parse_date(ns.report_date),
        skip_llm=ns.skip_llm,
    )
