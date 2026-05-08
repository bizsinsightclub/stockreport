"""거시 시리즈 수집.

USD/KRW 는 Frankfurter (https://www.frankfurter.app, ECB-sourced, 무료/무키)
를 1차 소스로 사용한다. Frankfurter 실패 시 pykrx 환율 함수를 fallback 으로
시도하고, 둘 다 실패하면 None 반환 (main.py 의 ``macro_skipped`` 가 처리).

다른 시리즈 (Clarkson 신조선가, DRAM DXI 등) 는 Phase 1 미지원.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

_FRANKFURTER_BASE = "https://api.frankfurter.app"
_TIMEOUT = 15


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, source: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"data": data, "source": source, "tool_args": args, "fetched_at": _now_iso_utc()}


def _yyyymmdd_to_iso(s: str) -> str:
    """``20260508`` → ``2026-05-08``."""
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def fetch_usdkrw_frankfurter(fromdate: str, todate: str) -> dict[str, Any]:
    """USD/KRW 일자별 환율 (Frankfurter range API).

    fromdate/todate 는 ``YYYYMMDD`` 또는 ``YYYY-MM-DD``.
    응답: ``[{"date": "YYYY-MM-DD", "종가": float}, ...]`` (analyzer 호환)
    """
    fd = _yyyymmdd_to_iso(fromdate)
    td = _yyyymmdd_to_iso(todate)
    url = f"{_FRANKFURTER_BASE}/{fd}..{td}"
    params = {"from": "USD", "to": "KRW"}
    logger.debug("frankfurter GET %s %s", url, params)

    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    rates: dict[str, dict[str, float]] = payload.get("rates", {}) or {}

    rows: list[dict[str, Any]] = []
    for d_str in sorted(rates.keys()):
        krw = rates[d_str].get("KRW")
        if krw is None:
            continue
        rows.append({"date": d_str, "종가": float(krw)})

    return _wrap(
        rows,
        "frankfurter:USD/KRW",
        {"fromdate": fd, "todate": td, "from": "USD", "to": "KRW"},
    )


def fetch_usdkrw_pykrx(fromdate: str, todate: str) -> dict[str, Any]:
    """pykrx 환율 fallback (오타 함수명 ``get_exhange_rate_by_date`` 도 처리)."""
    try:
        from pykrx import stock  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pykrx 미설치") from exc

    fn = getattr(stock, "get_exhange_rate_by_date", None) or getattr(
        stock, "get_exchange_rate_by_date", None
    )
    if fn is None:
        raise RuntimeError("pykrx 에 환율 함수가 없습니다 (버전 불일치)")

    df = fn(fromdate, todate, "USD")
    rows: list[dict[str, Any]] = []
    for d, row in df.iterrows():
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        item: dict[str, Any] = {"date": ds}
        for col, val in row.items():
            try:
                item[str(col)] = float(val) if val is not None else None
            except (ValueError, TypeError):
                item[str(col)] = val
        rows.append(item)

    return _wrap(
        rows,
        "pykrx:get_exhange_rate_by_date",
        {"fromdate": fromdate, "todate": todate, "currency": "USD"},
    )


def fetch_usdkrw(fromdate: str, todate: str) -> dict[str, Any]:
    """Frankfurter 우선, 실패 시 pykrx fallback."""
    try:
        return fetch_usdkrw_frankfurter(fromdate, todate)
    except Exception as exc:  # noqa: BLE001
        logger.warning("frankfurter USD/KRW 실패, pykrx fallback 시도: %s", exc)
        return fetch_usdkrw_pykrx(fromdate, todate)


def try_fetch_series(name: str, fromdate: str, todate: str) -> dict[str, Any] | None:
    """알려진 거시 시리즈만 수집. 미구현 시리즈는 None 반환."""
    if name == "USDKRW":
        try:
            return fetch_usdkrw(fromdate, todate)
        except Exception as exc:  # noqa: BLE001
            logger.warning("USDKRW fetch 실패: %s", exc)
            return None
    # 그 외는 Phase 1 미지원
    logger.info("거시 시리즈 '%s' 는 Phase 1 미지원 — silent skip", name)
    return None
