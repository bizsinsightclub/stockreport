"""pykrx 백업 collector — 시세 / 수급.

KRX OpenAPI 키 없이 동작. 모든 함수는 메타 트리플을 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, source: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"data": data, "source": source, "tool_args": args, "fetched_at": _now_iso_utc()}


def _df_to_records(df: Any) -> list[dict[str, Any]]:
    """pandas DataFrame → list[dict]. 인덱스가 날짜인 경우 ``date`` 키로 직렬화."""
    rows: list[dict[str, Any]] = []
    if df is None or len(df) == 0:
        return rows
    for d, row in df.iterrows():
        if hasattr(d, "strftime"):
            key = d.strftime("%Y-%m-%d")
        else:
            key = str(d)
        item: dict[str, Any] = {"date": key}
        for col, val in row.items():
            try:
                item[str(col)] = (
                    float(val)
                    if val is not None and str(val).strip() != ""
                    else None
                )
            except (ValueError, TypeError):
                item[str(col)] = val
        rows.append(item)
    return rows


def fetch_ohlcv(ticker: str, fromdate: str, todate: str) -> dict[str, Any]:
    """일별 OHLCV. 컬럼: 시가, 고가, 저가, 종가, 거래량, 거래대금, 등락률."""
    from pykrx import stock  # type: ignore

    df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)
    return _wrap(
        _df_to_records(df),
        "pykrx:get_market_ohlcv_by_date",
        {"ticker": ticker, "fromdate": fromdate, "todate": todate},
    )


def fetch_investor_flow(ticker: str, fromdate: str, todate: str) -> dict[str, Any]:
    """일별 외/기/개 순매수 시계열 (거래대금 기준).

    pykrx ``get_market_trading_value_by_date`` 컬럼 = 기관합계 / 기타법인 / 개인 / 외국인합계 / 전체.
    각 값은 해당 일자 net 거래대금 (단위 KRW).
    """
    from pykrx import stock  # type: ignore

    fn = getattr(stock, "get_market_trading_value_by_date", None)
    if fn is None:
        raise RuntimeError("pykrx 버전이 너무 낮습니다 — get_market_trading_value_by_date 필요")

    df = fn(fromdate, todate, ticker)
    return _wrap(
        _df_to_records(df),
        "pykrx:get_market_trading_value_by_date",
        {"ticker": ticker, "fromdate": fromdate, "todate": todate},
    )


def fetch_market_cap_today(today_yyyymmdd: str, market: str = "ALL") -> dict[str, Any]:
    """전 종목 시가총액 스냅샷."""
    from pykrx import stock  # type: ignore

    df = stock.get_market_cap_by_ticker(today_yyyymmdd, market=market)
    rows: list[dict[str, Any]] = []
    for tk, row in df.iterrows():
        item: dict[str, Any] = {"ticker": str(tk)}
        for col, val in row.items():
            try:
                item[str(col)] = (
                    float(val)
                    if val is not None and str(val).strip() != ""
                    else None
                )
            except (ValueError, TypeError):
                item[str(col)] = val
        rows.append(item)

    return _wrap(
        rows,
        "pykrx:get_market_cap_by_ticker",
        {"date": today_yyyymmdd, "market": market},
    )
