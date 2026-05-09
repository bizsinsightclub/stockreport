"""애널리스트 목표주가 (TP) 컨센서스 — 인터페이스 + 비활성 default.

⚠ 2026-05-09: 무료 한국 금융 컨센서스 사이트 (네이버 / 한경 / 다음 모바일) 의
robots.txt 가 모두 ``Disallow: /`` 로 일반 크롤러 차단 정책을 명시하고 있어
스크래핑 기반 provider 는 사용하지 않는다 (CLAUDE.md §4 준수).

향후 유료 API 키 (FnGuide / Refinitiv / Quantiwise 등) 가 준비되면
``BaseTPProvider`` 를 구현한 새 클래스를 만들고 ``fetch_tp_consensus(provider=...)``
에 주입하면 된다. ``main.py`` 의 호출은 현재 ``tp_meta = None`` 으로 우회 중.

``NaverTPProvider`` 는 약관 검증을 위한 reference 코드로만 보존 — main.py 에서
호출하지 않는다. 활성화 시 robots.txt 재확인 + 약관 검토 필요.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) reporter-bot/0.1 "
    "(+https://github.com/bizsinsightclub/stockreport)"
)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        s = str(v).replace(",", "").strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _opinion_label(recomm_mean: float | None) -> str:
    """recommMean (1=매도, 5=매수) → 한국어 라벨."""
    if recomm_mean is None:
        return "—"
    if recomm_mean >= 4.5:
        return "강력매수"
    if recomm_mean >= 3.5:
        return "매수"
    if recomm_mean >= 2.5:
        return "중립"
    if recomm_mean >= 1.5:
        return "매도"
    return "강력매도"


class BaseTPProvider(ABC):
    """TP 컨센서스 공급자 인터페이스. 새 데이터 소스 추가 시 이 ABC 구현."""

    name: str = "base"

    @abstractmethod
    def fetch(self, ticker: str) -> dict[str, Any]:
        """``{tp_avg, opinion_mean, opinion_label, create_date, ...}`` 또는 빈 dict."""
        ...


class NaverTPProvider(BaseTPProvider):
    """네이버 finance 모바일 JSON API."""

    name = "naver"
    _BASE = "https://m.stock.naver.com/api/stock"
    _SLEEP_SEC = 1.0  # 1 종목당 1초 매너

    def fetch(self, ticker: str) -> dict[str, Any]:
        url = f"{self._BASE}/{ticker}/integration"
        headers = {"User-Agent": _DEFAULT_UA, "Accept": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=_DEFAULT_TIMEOUT)
            time.sleep(self._SLEEP_SEC)
        except requests.RequestException as exc:
            logger.warning("네이버 TP fetch 실패 %s: %s", ticker, exc)
            return {}
        if resp.status_code != 200:
            logger.info("네이버 TP %s status=%s", ticker, resp.status_code)
            return {}
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("네이버 TP %s JSON 파싱 실패", ticker)
            return {}

        ci = payload.get("consensusInfo")
        if not ci:
            return {}

        tp_avg = _to_float(ci.get("priceTargetMean"))
        recomm = _to_float(ci.get("recommMean"))
        return {
            "tp_avg": tp_avg,
            "opinion_mean": recomm,
            "opinion_label": _opinion_label(recomm),
            "create_date": ci.get("createDate"),
        }


def fetch_tp_consensus(
    ticker: str,
    *,
    current_price: float | None = None,
    provider: BaseTPProvider | None = None,
) -> dict[str, Any]:
    """TP 컨센서스 fetch + 메타 트리플 wrap. 데이터가 없으면 ``data={}``.

    ``current_price`` 가 주어지면 ``upside_pct`` 도 계산.
    """
    p = provider or NaverTPProvider()
    raw = p.fetch(ticker)

    if raw and raw.get("tp_avg") and current_price:
        upside = (raw["tp_avg"] - current_price) / current_price * 100.0
        raw["upside_pct"] = round(upside, 2)
        raw["current_price"] = current_price

    return {
        "data": raw,
        "source": f"tp-consensus:{p.name}",
        "tool_args": {"ticker": ticker},
        "fetched_at": _now_iso_utc(),
    }
