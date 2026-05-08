"""KRX OpenAPI (data-dbg.krx.co.kr/svc/apis) 호출.

엔드포인트 (요청 시 ``AUTH_KEY`` 헤더에 발급키, 쿼리에 ``basDd``=YYYYMMDD):
- ``sto/stk_bydd_trd``        KOSPI 종목별 일별 매매정보
- ``sto/ksq_bydd_trd``        KOSDAQ 종목별 일별 매매정보
- ``sto/stk_isu_base_info``   주식 기본정보 (업종/시장 분류)
- ``sto/sto_inv_invr_dd_trd`` 투자자별 일별 거래실적

키 미발급/엔드포인트 미인가 시 호출부에서 pykrx fallback 으로 우회.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE = "http://data-dbg.krx.co.kr/svc/apis"
_TIMEOUT = 15
_RETRY_5XX = 1  # 5xx 한 번 재시도


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, source: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": data,
        "source": source,
        "tool_args": args,
        "fetched_at": _now_iso_utc(),
    }


def _api_key() -> str | None:
    return os.environ.get("KRX_API_KEY") or None


def _get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """KRX OpenAPI 호출 + 5xx 1회 재시도. 4xx 는 즉시 raise."""
    key = _api_key()
    if not key:
        raise RuntimeError("KRX_API_KEY 미설정")

    url = f"{_BASE}/{endpoint}"
    headers = {"AUTH_KEY": key}
    logger.debug("KRX GET %s params=%s", url, params)

    last_exc: Exception | None = None
    for attempt in range(_RETRY_5XX + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _RETRY_5XX:
                time.sleep(0.5)
                continue
            raise

        logger.info("KRX %s status=%s", endpoint, resp.status_code)
        if resp.status_code >= 500 and attempt < _RETRY_5XX:
            time.sleep(0.5)
            continue
        if not resp.ok:
            # 4xx 본문에 KRX 에러 메시지가 들어있음 — 그대로 노출
            raise RuntimeError(
                f"KRX {endpoint} HTTP {resp.status_code}: {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"KRX {endpoint} 응답이 JSON 이 아님: {resp.text[:200]}"
            ) from exc
    if last_exc:
        raise last_exc
    raise RuntimeError(f"KRX {endpoint} unreachable")


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """KRX 응답은 보통 ``{"OutBlock_1": [...]}`` 또는 ``{"output": [...]}``."""
    if not isinstance(payload, dict):
        return []
    for key in ("OutBlock_1", "OutBlock_2", "output", "block1"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
    # 알 수 없는 형태 — list 값을 가진 첫 키 반환
    for v in payload.values():
        if isinstance(v, list):
            return v
    return []


def _market_endpoint(market: str) -> str:
    market = market.upper()
    return {
        "STK": "sto/stk_bydd_trd",  # KOSPI
        "KSQ": "sto/ksq_bydd_trd",  # KOSDAQ
        "KNX": "sto/knx_bydd_trd",  # KONEX
    }.get(market, "")


def fetch_market_cap_ranking(market: str, basDd: str) -> dict[str, Any]:
    """전 종목 일별 매매정보. ``MKTCAP`` 컬럼으로 시총 랭킹 산출 가능.

    market ∈ {"STK","KSQ","KNX"}.
    """
    endpoint = _market_endpoint(market)
    if not endpoint:
        raise ValueError(f"unknown market: {market}")

    payload = _get(endpoint, {"basDd": basDd})
    rows = _extract_rows(payload)
    return _wrap(
        rows,
        f"krx-openapi:{endpoint}",
        {"market": market, "basDd": basDd},
    )


def fetch_stock_base_info(ticker: str, basDd: str) -> dict[str, Any]:
    """종목 기본정보. 응답에 ``IDX_IND_NM`` (업종지수명) 등이 들어있음."""
    payload = _get("sto/stk_isu_base_info", {"basDd": basDd})
    rows = _extract_rows(payload)
    matched = [
        r for r in rows
        if str(r.get("ISU_SRT_CD") or r.get("isu_srt_cd") or "").strip() == str(ticker)
    ]
    return _wrap(
        matched,
        "krx-openapi:sto/stk_isu_base_info",
        {"ticker": ticker, "basDd": basDd},
    )


def fetch_investor_flow_daily(ticker: str, basDd: str) -> dict[str, Any]:
    """투자자별 일별 거래실적 (특정 일자, 특정 종목 필터)."""
    payload = _get("sto/sto_inv_invr_dd_trd", {"basDd": basDd})
    rows = _extract_rows(payload)
    matched = [
        r for r in rows
        if str(r.get("ISU_SRT_CD") or r.get("isu_srt_cd") or "").strip() == str(ticker)
    ]
    return _wrap(
        matched,
        "krx-openapi:sto/sto_inv_invr_dd_trd",
        {"ticker": ticker, "basDd": basDd},
    )


def _parse_yyyymmdd(s: str) -> date:
    return datetime.strptime(s, "%Y%m%d").date()


def fetch_investor_flow_range(
    ticker: str,
    fromdate: str,
    todate: str,
    *,
    sleep_sec: float = 0.15,
) -> dict[str, Any]:
    """``fromdate~todate`` 사이 영업일 별 호출 후 누적.

    KRX OpenAPI 는 단일 ``basDd`` 만 받으므로 일자 루프가 필수.
    """
    start = _parse_yyyymmdd(fromdate)
    end = _parse_yyyymmdd(todate)

    aggregated: list[dict[str, Any]] = []
    cur = start
    failures = 0
    while cur <= end:
        # 토/일 skip — 휴장일 호출은 KRX 가 빈 결과로 응답하므로 굳이 막지 않아도 OK
        if cur.weekday() < 5:
            day = cur.strftime("%Y%m%d")
            try:
                day_payload = _get("sto/sto_inv_invr_dd_trd", {"basDd": day})
                rows = _extract_rows(day_payload)
                for r in rows:
                    code = str(r.get("ISU_SRT_CD") or r.get("isu_srt_cd") or "").strip()
                    if code == str(ticker):
                        # basDd 정보 부족 시 보강
                        r.setdefault("BAS_DD", day)
                        aggregated.append(r)
                time.sleep(sleep_sec)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                logger.warning("KRX flow %s 실패: %s", day, exc)
                if failures >= 3:
                    # 인증 문제로 보임 — 더 이상 시도하지 않고 raise
                    raise
        cur += timedelta(days=1)

    return _wrap(
        aggregated,
        "krx-openapi:sto/sto_inv_invr_dd_trd",
        {"ticker": ticker, "fromdate": fromdate, "todate": todate},
    )
