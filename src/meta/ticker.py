"""ticker → name / market / sector_code 해석.

pykrx 를 1차로 사용하고 실패 시 빈 값으로 degrade. 본 모듈은 외부 호출이지만
analyzers/renderer 에서 import 하지 않으므로 의존성 그래프상 ``meta``는 데이터
계층으로 본다 (CLAUDE.md §2 의 mcp_clients/collectors 와 동등).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TickerMeta:
    ticker: str
    name: str
    market: str  # "KOSPI" | "KOSDAQ" | "KONEX" | ""
    sector_code: str  # 업종코드 (없으면 "")
    sector_name: str  # 업종명 (없으면 "")


def _safe_pykrx() -> object | None:
    try:
        from pykrx import stock  # type: ignore

        return stock
    except ImportError:
        return None


def resolve(ticker: str) -> TickerMeta:
    """ticker → (name, market, sector). 실패해도 ticker만 채워서 반환."""
    stk = _safe_pykrx()
    name = ""
    market = ""
    sector_code = ""
    sector_name = ""

    if stk is not None:
        try:
            name = stk.get_market_ticker_name(ticker) or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("pykrx ticker name 실패 (%s): %s", ticker, exc)

        for cand in ("KOSPI", "KOSDAQ", "KONEX"):
            try:
                tickers = stk.get_market_ticker_list(market=cand) or []
            except Exception:  # noqa: BLE001
                continue
            if ticker in tickers:
                market = cand
                break

        # pykrx 가 섹터 분류를 직접 노출하지 않을 수 있다.
        # 시도하되 실패하면 graceful degrade.
        try:
            df = stk.get_market_sector_classifications(  # type: ignore[attr-defined]
                "ALL"
            )
            row = df[df.index == ticker] if df is not None else None
            if row is not None and len(row) > 0:
                sector_name = str(row.iloc[0].get("업종명", ""))
                sector_code = str(row.iloc[0].get("업종코드", ""))
        except Exception:
            # 함수가 없거나 실패 — Phase 1 에서 silent degrade
            pass

    return TickerMeta(
        ticker=ticker,
        name=name,
        market=market,
        sector_code=sector_code,
        sector_name=sector_name,
    )
