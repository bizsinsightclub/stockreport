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
    """일별 OHLCV. 컬럼: 시가, 고가, 저가, 종가, 거래량, 거래대금, 등락률.

    pykrx 1.2.x 는 ``adjusted=True`` (default) 시 거래대금 컬럼을 누락하므로
    ``adjusted=False`` 로 호출. 단기(~6M) 분석이라 수정주가 정합성 영향 minimal.
    """
    from pykrx import stock  # type: ignore

    df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker, adjusted=False)
    return _wrap(
        _df_to_records(df),
        "pykrx:get_market_ohlcv_by_date",
        {"ticker": ticker, "fromdate": fromdate, "todate": todate, "adjusted": False},
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


def fetch_market_fundamental(ticker: str, today_yyyymmdd: str) -> dict[str, Any]:
    """pykrx ``get_market_fundamental_by_date`` — BPS/PER/PBR/EPS/DIV/DPS.

    KRX_ID/KRX_PW 인증 필요. 적자 종목은 PER/EPS 가 0 으로 반환됨.
    """
    from pykrx import stock  # type: ignore

    df = stock.get_market_fundamental_by_date(today_yyyymmdd, today_yyyymmdd, ticker)
    payload: dict[str, Any] = {}
    if df is not None and len(df) > 0:
        row = df.iloc[0]
        for key in ("BPS", "PER", "PBR", "EPS", "DIV", "DPS"):
            try:
                payload[key] = float(row.get(key, 0) or 0)
            except (ValueError, TypeError):
                payload[key] = None
    return _wrap(
        payload,
        "pykrx:get_market_fundamental_by_date",
        {"ticker": ticker, "date": today_yyyymmdd},
    )


def fetch_market_cap_single(ticker: str, today_yyyymmdd: str) -> dict[str, Any]:
    """단일 종목 시가총액 (단일 일자). 회전율 계산용."""
    from pykrx import stock  # type: ignore

    df = stock.get_market_cap_by_date(today_yyyymmdd, today_yyyymmdd, ticker)
    payload: dict[str, Any] = {}
    if df is not None and len(df) > 0:
        row = df.iloc[0]
        for col in ("시가총액", "거래량", "거래대금", "상장주식수"):
            try:
                v = row.get(col)
                payload[col] = float(v) if v is not None else None
            except (ValueError, TypeError):
                payload[col] = None
    return _wrap(
        payload,
        "pykrx:get_market_cap_by_date",
        {"ticker": ticker, "date": today_yyyymmdd},
    )


def fetch_etf_market(today_yyyymmdd: str) -> dict[str, Any]:
    """pykrx ``get_etf_ohlcv_by_ticker`` — 시장 전체 ETF 단일일자.

    KRX OpenAPI ``etp/etf_bydd_trd`` 가 미승인일 때의 fallback. 컬럼:
    NAV / 시가 / 고가 / 저가 / 종가 / 거래량 / 거래대금 / 기초지수.

    상장좌수·시가총액은 별도 ``get_market_cap_by_ticker`` 결합 필요.
    """
    from pykrx import stock  # type: ignore

    rows: list[dict[str, Any]] = []
    try:
        df = stock.get_etf_ohlcv_by_ticker(today_yyyymmdd)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ETF 시장 fetch 실패: %s", exc)
        return _wrap([], "pykrx:get_etf_ohlcv_by_ticker", {"date": today_yyyymmdd})

    if df is None or len(df) == 0:
        return _wrap([], "pykrx:get_etf_ohlcv_by_ticker", {"date": today_yyyymmdd})

    # 시총·상장좌수 맵 — 별도 호출
    cap_map: dict[str, dict[str, Any]] = {}
    try:
        cap_df = stock.get_market_cap_by_ticker(today_yyyymmdd, market="ALL")
        for tk, row in cap_df.iterrows():
            cap_map[str(tk)] = {
                "시가총액": row.get("시가총액"),
                "상장주식수": row.get("상장주식수"),
            }
    except Exception:  # noqa: BLE001
        cap_map = {}

    for tk, row in df.iterrows():
        item: dict[str, Any] = {"ISU_CD": str(tk)}
        try:
            item["ISU_NM"] = stock.get_etf_ticker_name(str(tk))
        except Exception:  # noqa: BLE001
            item["ISU_NM"] = ""
        for col in df.columns:
            v = row.get(col)
            try:
                item[str(col)] = float(v) if v is not None else None
            except (ValueError, TypeError):
                item[str(col)] = v
        cap = cap_map.get(str(tk), {})
        item["MKTCAP"] = float(cap.get("시가총액") or 0) if cap.get("시가총액") is not None else None
        item["LIST_SHRS"] = float(cap.get("상장주식수") or 0) if cap.get("상장주식수") is not None else None
        rows.append(item)

    return _wrap(rows, "pykrx:get_etf_ohlcv_by_ticker", {"date": today_yyyymmdd})


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
