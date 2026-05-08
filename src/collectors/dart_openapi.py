"""DART OpenAPI 직접 호출.

엔드포인트:
- ``list.json``               공시 검색
- ``corpCode.xml``            전 기업 corp_code↔stock_code (zip→xml)
- ``fnlttSinglAcntAll.json``  단일회사 전체 재무제표 (사업/반기/분기)

corp_code map 은 ``data/cache/corp_code.json`` 에 24h TTL 로 캐시.
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE = "https://opendart.fss.or.kr/api"
_TIMEOUT = 30
_CACHE_TTL_SEC = 24 * 3600


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(data: Any, source: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"data": data, "source": source, "tool_args": args, "fetched_at": _now_iso_utc()}


def _api_key() -> str | None:
    return os.environ.get("DART_API_KEY") or None


def _cache_path() -> Path:
    # config.py 의 DATA_DIR 를 직접 import 하지 않고 상대 위치 추정
    # (collectors 는 main.py 외 어디서도 import 되지 않으므로 안전)
    here = Path(__file__).resolve().parents[2]  # .../reporter/
    return here / "data" / "cache" / "corp_code.json"


# ─── 공시 검색 ───────────────────────────────────────────────────────


def fetch_disclosure_list(
    corp_code: str | None,
    bgn_de: str,
    end_de: str,
    *,
    page_count: int = 30,
) -> dict[str, Any]:
    """공시 검색 (``list.json``).

    bgn_de/end_de 는 ``YYYYMMDD`` 또는 ``YYYY-MM-DD`` (DART 는 YYYYMMDD 만 허용 →
    하이픈 자동 제거).
    """
    key = _api_key()
    if not key:
        raise RuntimeError("DART_API_KEY 미설정")

    bgn = bgn_de.replace("-", "")
    end = end_de.replace("-", "")

    params: dict[str, Any] = {
        "crtfc_key": key,
        "bgn_de": bgn,
        "end_de": end,
        "page_count": page_count,
    }
    if corp_code:
        params["corp_code"] = corp_code

    url = f"{_BASE}/list.json"
    logger.debug("DART GET %s %s", url, {**params, "crtfc_key": "***"})
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    status = payload.get("status")
    if status not in ("000", "013"):
        # 013 = 조회된 데이터 없음 (정상 처리)
        logger.warning("DART list.json status=%s msg=%s", status, payload.get("message"))
    rows = payload.get("list", []) if isinstance(payload, dict) else []
    return _wrap(
        rows,
        "dart-openapi:list.json",
        {"corp_code": corp_code, "bgn_de": bgn, "end_de": end},
    )


# ─── corp_code map ─────────────────────────────────────────────────


def fetch_corp_code_map() -> dict[str, Any]:
    """전체 기업 corp_code (zip → xml) 를 list[dict] 로 반환."""
    key = _api_key()
    if not key:
        raise RuntimeError("DART_API_KEY 미설정")

    url = f"{_BASE}/corpCode.xml"
    resp = requests.get(url, params={"crtfc_key": key}, timeout=_TIMEOUT)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(zf.namelist()[0]) as fh:
            root = ET.parse(fh).getroot()

    rows: list[dict[str, str]] = []
    for elem in root.findall("list"):
        rows.append(
            {
                "corp_code": _text(elem, "corp_code"),
                "corp_name": _text(elem, "corp_name"),
                "stock_code": _text(elem, "stock_code"),
                "modify_date": _text(elem, "modify_date"),
            }
        )
    return _wrap(rows, "dart-openapi:corpCode.xml", {})


def _text(elem: ET.Element, tag: str) -> str:
    node = elem.find(tag)
    return (node.text or "").strip() if node is not None and node.text else ""


def _load_cached_corp_codes() -> list[dict[str, str]] | None:
    path = _cache_path()
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > _CACHE_TTL_SEC:
        logger.info("corp_code 캐시 만료 (%.0fs)", age)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("corp_code 캐시 로드 실패: %s", exc)
        return None


def _save_cached_corp_codes(rows: list[dict[str, str]]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def lookup_corp_code(stock_code: str) -> str | None:
    """6자리 ``stock_code`` → ``corp_code``. 없으면 None.

    ``data/cache/corp_code.json`` 24h 캐시. 만료 시 재다운로드.
    """
    rows = _load_cached_corp_codes()
    if rows is None:
        try:
            meta = fetch_corp_code_map()
            rows = meta["data"]
            _save_cached_corp_codes(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("corp_code map 다운로드 실패: %s", exc)
            return None

    target = str(stock_code).strip()
    for r in rows:
        if r.get("stock_code", "").strip() == target:
            return r.get("corp_code") or None
    return None


# ─── 재무제표 ───────────────────────────────────────────────────────


_REPRT_CODE_BY_QUARTER = {
    1: "11013",  # 1분기
    2: "11012",  # 반기
    3: "11014",  # 3분기
}
_REPRT_CODE_ANNUAL = "11011"  # 사업보고서


def _fetch_fnltt(corp_code: str, year: int, reprt_code: str) -> dict[str, Any]:
    key = _api_key()
    if not key:
        raise RuntimeError("DART_API_KEY 미설정")

    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": reprt_code,
        "fs_div": "CFS",  # 연결재무제표 (없으면 caller 가 OFS fallback)
    }
    url = f"{_BASE}/fnlttSinglAcntAll.json"
    logger.debug("DART GET %s yr=%s rc=%s", url, year, reprt_code)
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    status = payload.get("status")
    if status != "000":
        # 013 = 데이터 없음. CFS 없으면 OFS 재시도
        if status == "013" and params["fs_div"] == "CFS":
            params["fs_div"] = "OFS"
            resp2 = requests.get(url, params=params, timeout=_TIMEOUT)
            resp2.raise_for_status()
            payload = resp2.json()
            status = payload.get("status")
        if status != "000":
            raise RuntimeError(
                f"DART fnlttSinglAcntAll status={status} msg={payload.get('message')}"
            )
    rows = payload.get("list", [])
    return _wrap(
        rows,
        "dart-openapi:fnlttSinglAcntAll.json",
        {
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": reprt_code,
            "fs_div": params["fs_div"],
        },
    )


def fetch_financials_annual(corp_code: str, year: int) -> dict[str, Any]:
    """사업보고서 (연간) 전체 재무제표."""
    return _fetch_fnltt(corp_code, year, _REPRT_CODE_ANNUAL)


def fetch_financials_quarterly(corp_code: str, year: int, quarter: int) -> dict[str, Any]:
    """분기/반기 보고서. ``quarter`` ∈ {1,2,3}."""
    rc = _REPRT_CODE_BY_QUARTER.get(quarter)
    if rc is None:
        raise ValueError(f"unsupported quarter: {quarter}")
    return _fetch_fnltt(corp_code, year, rc)
