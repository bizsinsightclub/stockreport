"""korea-stock-mcp 도메인 래퍼.

모든 ``fetch_*`` 함수는 메타 트리플(CLAUDE.md §3.1)을 반환한다::

    {"data": ..., "source": "korea-stock-mcp:<tool>",
     "tool_args": {...}, "fetched_at": "<ISO 8601 UTC>"}

⚠ ``_TOOLS`` 의 키는 추정값. 첫 실행 시 ``python -m src.mcp_clients.client --list``
로 실제 도구명을 확인하고 보정할 것 (HANDOFF §5.1).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.config import KOREA_STOCK_MCP

logger = logging.getLogger(__name__)


# 추정 매핑 — 첫 실행 후 검증/보정 필요.
_TOOLS: dict[str, str] = {
    "stock_price": "get_stock_price",
    "disclosure_list": "get_disclosure_list",
    "financials": "get_financials",
    "investor_flow": "get_investor_flow",
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": data,
        "source": f"korea-stock-mcp:{tool}",
        "tool_args": args,
        "fetched_at": _now_iso_utc(),
    }


async def _safe_call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """call_tool 을 실행하고 메타 트리플로 감싼다. 실패 시 예외 재발생."""
    from src.mcp_clients.client import call_tool

    logger.info("MCP call: %s args=%s", tool, args)
    data = await call_tool(KOREA_STOCK_MCP, tool, args)
    return _wrap(data, tool, args)


async def fetch_stock_price(
    ticker: str, fromdate: str, todate: str
) -> dict[str, Any]:
    """일별 OHLCV 시세."""
    tool = _TOOLS["stock_price"]
    return await _safe_call(
        tool,
        {"ticker": ticker, "fromdate": fromdate, "todate": todate},
    )


async def fetch_disclosure_list(
    corp_name: str, fromdate: str, todate: str
) -> dict[str, Any]:
    """DART 공시 리스트."""
    tool = _TOOLS["disclosure_list"]
    return await _safe_call(
        tool,
        {"corp_name": corp_name, "fromdate": fromdate, "todate": todate},
    )


async def fetch_financials(ticker: str) -> dict[str, Any]:
    """분기별 재무제표 (XBRL 기반)."""
    tool = _TOOLS["financials"]
    return await _safe_call(tool, {"ticker": ticker})


async def fetch_investor_flow(
    ticker: str, fromdate: str, todate: str
) -> dict[str, Any]:
    """외국인/기관/개인 순매수 추이."""
    tool = _TOOLS["investor_flow"]
    return await _safe_call(
        tool,
        {"ticker": ticker, "fromdate": fromdate, "todate": todate},
    )
