"""KRX OpenAPI — ETP 카테고리 (ETF / ETN / ELW 일별매매정보).

Endpoint:
- ``etp/etf_bydd_trd``  ETF 일별매매정보
- ``etp/etn_bydd_trd``  ETN 일별매매정보
- ``etp/elw_bydd_trd``  ELW 일별매매정보

⚠ 모든 ETP API 는 KRX OpenAPI 포털에서 별도 구독 신청·승인 필요. 미승인 상태에서는
401 반환. 본 모듈은 401 시 빈 dict + ``status=401`` 메타로 graceful degrade.

CLAUDE.md §3.1 메타 트리플 wrap. 호출자가 ``data`` 빈 list 인지 확인 후 fallback 처리.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE = "https://data-dbg.krx.co.kr/svc/apis"
_TIMEOUT = 15


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, source: str, args: dict[str, Any], status: int = 200) -> dict[str, Any]:
    return {
        "data": data,
        "source": source,
        "tool_args": args,
        "fetched_at": _now_iso_utc(),
        "status": status,
    }


def _fetch(path: str, basdd_yyyymmdd: str) -> dict[str, Any]:
    """공통 fetcher — 401 graceful, 200이면 OutBlock_1 list 반환."""
    key = os.environ.get("KRX_API_KEY")
    if not key:
        return _wrap([], f"krx-openapi:{path}", {"basDd": basdd_yyyymmdd}, status=0)

    url = f"{_BASE}/{path}"
    try:
        resp = requests.get(
            url,
            headers={"AUTH_KEY": key},
            params={"basDd": basdd_yyyymmdd},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("KRX %s fetch 실패: %s", path, exc)
        return _wrap([], f"krx-openapi:{path}", {"basDd": basdd_yyyymmdd}, status=-1)

    if resp.status_code != 200:
        logger.info(
            "KRX %s status=%s (%s 미승인 가능성)",
            path,
            resp.status_code,
            "API 신청 필요" if resp.status_code == 401 else "기타",
        )
        return _wrap([], f"krx-openapi:{path}", {"basDd": basdd_yyyymmdd}, status=resp.status_code)

    try:
        payload = resp.json()
    except ValueError:
        return _wrap([], f"krx-openapi:{path}", {"basDd": basdd_yyyymmdd}, status=resp.status_code)
    rows = payload.get("OutBlock_1", []) or []
    return _wrap(rows, f"krx-openapi:{path}", {"basDd": basdd_yyyymmdd}, status=200)


def fetch_etf_bydd_trd(basdd_yyyymmdd: str) -> dict[str, Any]:
    """ETF 일별매매정보 — 1099개 종목 NAV/시가/종가/거래량/거래대금/시총/상장좌수/기초지수."""
    return _fetch("etp/etf_bydd_trd", basdd_yyyymmdd)


def fetch_etn_bydd_trd(basdd_yyyymmdd: str) -> dict[str, Any]:
    """ETN 일별매매정보 — 393개 ETN 매매정보 + IV(지표가치) + 기초지수."""
    return _fetch("etp/etn_bydd_trd", basdd_yyyymmdd)


def fetch_elw_bydd_trd(basdd_yyyymmdd: str) -> dict[str, Any]:
    """ELW 일별매매정보 — 2528개 워런트 매매정보 + 기초자산."""
    return _fetch("etp/elw_bydd_trd", basdd_yyyymmdd)
