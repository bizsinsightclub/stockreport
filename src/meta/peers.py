"""피어 자동 선정.

전략 (시도 순서):
1. ``override`` 가 주어지면 그대로 반환 (검증만).
2. KRX OpenAPI ``stk_isu_base_info`` 의 ``IDX_IND_CD`` 매칭. (포털 승인 필요)
3. **DART induty_code 매칭** — 시총 상위 풀에서 KSIC 5자리 → 4자리 → 3자리 prefix 매칭.
4. pykrx ``get_market_cap_by_ticker`` 시총 상위 N (섹터 무관, ``degraded=True``).

DART 경로의 induty_code 는 ``data/cache/induty_code.json`` 24h 캐시.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PeerSelection:
    peers: list[str]
    degraded: bool
    note: str


def _safe_pykrx() -> object | None:
    try:
        from pykrx import stock  # type: ignore

        return stock
    except ImportError:
        return None


def _try_krx_openapi(target_ticker: str, today_yyyymmdd: str, n: int) -> tuple[list[str], str] | None:
    """KRX OpenAPI 로 KOSPI+KOSDAQ 시총 랭킹 + (가능 시) 같은 업종 필터.

    실패 시 None. 성공 시 ``(peers, note)``.
    """
    try:
        from src.collectors import krx_openapi as krx
    except ImportError:
        return None

    try:
        kospi = krx.fetch_market_cap_ranking("STK", today_yyyymmdd)
        kosdaq = krx.fetch_market_cap_ranking("KSQ", today_yyyymmdd)
    except Exception as exc:  # noqa: BLE001
        logger.warning("KRX OpenAPI 시총 랭킹 실패: %s", exc)
        return None

    rows: list[dict[str, Any]] = list(kospi.get("data") or []) + list(kosdaq.get("data") or [])
    if not rows:
        return None

    # MKTCAP 컬럼은 문자열 (콤마 포함) 가능 — float 정규화
    def _mktcap(r: dict[str, Any]) -> float:
        v = r.get("MKTCAP") or r.get("mktcap") or 0
        try:
            return float(str(v).replace(",", ""))
        except ValueError:
            return 0.0

    def _ticker(r: dict[str, Any]) -> str:
        return str(r.get("ISU_SRT_CD") or r.get("isu_srt_cd") or "").strip()

    def _sector(r: dict[str, Any]) -> str:
        return str(
            r.get("IDX_IND_NM") or r.get("idx_ind_nm")
            or r.get("IDX_IND_CD") or r.get("idx_ind_cd")
            or ""
        ).strip()

    target_row = next((r for r in rows if _ticker(r) == target_ticker), None)
    target_sector = _sector(target_row) if target_row else ""

    rows_sorted = sorted(rows, key=_mktcap, reverse=True)

    if target_sector:
        same_sector = [
            r for r in rows_sorted
            if _sector(r) == target_sector and _ticker(r) != target_ticker
        ]
        if same_sector:
            peers = [_ticker(r) for r in same_sector[:n] if _ticker(r)]
            if peers:
                return peers, ""  # 정상 (degrade 아님)

    fallback = [
        _ticker(r) for r in rows_sorted
        if _ticker(r) and _ticker(r) != target_ticker
    ][:n]
    if not fallback:
        return None
    return fallback, "KRX 업종 매칭 실패 — 시총 상위로 대체"


def _detect_market(stk: Any, target_ticker: str, today_yyyymmdd: str) -> str:
    """target 이 KOSPI 인지 KOSDAQ 인지 — pykrx ticker list 로 판별. 실패 시 'ALL'."""
    try:
        if target_ticker in stk.get_market_ticker_list(today_yyyymmdd, market="KOSPI"):
            return "KOSPI"
        if target_ticker in stk.get_market_ticker_list(today_yyyymmdd, market="KOSDAQ"):
            return "KOSDAQ"
    except Exception:  # noqa: BLE001
        pass
    return "ALL"


# DART induty 매칭에서 보는 시총 상위 풀 크기
_INDUTY_POOL_SIZE = 250


def _try_dart_induty(target_ticker: str, today_yyyymmdd: str, n: int) -> tuple[list[str], str] | None:
    """DART ``company.json`` 의 KSIC ``induty_code`` 로 같은 산업 매칭.

    1. target induty_code 조회.
    2. 같은 시장 (KOSPI/KOSDAQ) 시총 상위 ``_INDUTY_POOL_SIZE`` 의 induty_code 일괄 조회 (캐시).
    3. 5자리 → 4자리 → 3자리 prefix 매칭 단계 확장.
    """
    stk = _safe_pykrx()
    if stk is None:
        return None

    try:
        from src.collectors import dart_openapi as dart
    except ImportError:
        return None

    target_ind = dart.lookup_induty_code(target_ticker)
    if not target_ind:
        return None

    market = _detect_market(stk, target_ticker, today_yyyymmdd)
    try:
        cap_df = stk.get_market_cap_by_ticker(today_yyyymmdd, market=market)
    except Exception as exc:  # noqa: BLE001
        logger.warning("induty 경로 시총 조회 실패: %s", exc)
        return None
    if cap_df is None or len(cap_df) == 0:
        return None

    sorted_caps = cap_df.sort_values("시가총액", ascending=False)
    pool_tickers = [
        str(tk) for tk in sorted_caps.index[: _INDUTY_POOL_SIZE]
        if str(tk) != target_ticker
    ]

    induty_map = dart.bulk_lookup_induty_codes(pool_tickers)
    candidates = [
        (tk, induty_map.get(tk, ""), int(sorted_caps.loc[tk, "시가총액"]))
        for tk in pool_tickers
        if induty_map.get(tk)
    ]

    for prefix_len in (5, 4, 3):
        same = [
            (tk, cap) for (tk, ind, cap) in candidates
            if ind[:prefix_len] == target_ind[:prefix_len]
        ]
        same.sort(key=lambda x: x[1], reverse=True)
        if len(same) >= max(1, min(n, 2)):
            peers = [tk for (tk, _) in same[:n]]
            note = f"DART induty {target_ind} ({prefix_len}자리 prefix, market={market})"
            return peers, note

    return None


def _try_pykrx(target_ticker: str, sector_code: str, today_yyyymmdd: str, n: int) -> tuple[list[str], bool, str]:
    """pykrx ``get_market_cap_by_ticker`` fallback. (peers, degraded, note)."""
    stk = _safe_pykrx()
    if stk is None:
        return [], True, "pykrx 미설치"

    try:
        cap_df = stk.get_market_cap_by_ticker(today_yyyymmdd, market="ALL")
    except Exception as exc:  # noqa: BLE001
        logger.warning("pykrx 시총 조회 실패: %s", exc)
        return [], True, f"pykrx 시총 조회 실패: {exc}"

    if cap_df is None or len(cap_df) == 0:
        return [], True, "pykrx 시총 비어있음"

    sorted_caps = cap_df.sort_values("시가총액", ascending=False)

    sector_df = None
    try:
        sector_df = stk.get_market_sector_classifications("ALL")  # type: ignore[attr-defined]
    except Exception:
        sector_df = None

    if sector_code and sector_df is not None and len(sector_df) > 0:
        try:
            same = sector_df[sector_df["업종코드"].astype(str) == str(sector_code)]
            tickers_in_sector = set(same.index.astype(str))
            in_sector = [
                str(tk) for tk in sorted_caps.index
                if str(tk) in tickers_in_sector and str(tk) != target_ticker
            ]
            if in_sector:
                return in_sector[:n], False, ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("섹터 필터 실패: %s", exc)

    fallback = [
        str(tk) for tk in sorted_caps.index if str(tk) != target_ticker
    ][:n]
    return fallback, True, "섹터 분류 미해결 — 시총 상위로 대체 선정"


def auto_select(
    target_ticker: str,
    sector_code: str,
    *,
    n: int = 5,
    today_yyyymmdd: str,
    market_cap_provider=None,
    sector_provider=None,
) -> PeerSelection:
    """피어 자동 선정 — KRX OpenAPI 우선, pykrx fallback."""

    # 테스트 주입 경로 (기존 시그니처 보존)
    if market_cap_provider is not None:
        cap_df = market_cap_provider(today_yyyymmdd)
        if cap_df is None or len(cap_df) == 0:
            return PeerSelection(peers=[], degraded=True, note="시총 데이터 미수집 — 피어 비어있음")
        sorted_caps = cap_df.sort_values("시가총액", ascending=False)
        sector_df = sector_provider() if sector_provider else None
        if sector_code and sector_df is not None and len(sector_df) > 0:
            try:
                same = sector_df[sector_df["업종코드"].astype(str) == str(sector_code)]
                tickers = set(same.index.astype(str))
                in_sector = [
                    str(tk) for tk in sorted_caps.index
                    if str(tk) in tickers and str(tk) != target_ticker
                ]
                if in_sector:
                    return PeerSelection(in_sector[:n], False, "")
            except Exception:
                pass
        fb = [str(tk) for tk in sorted_caps.index if str(tk) != target_ticker][:n]
        return PeerSelection(fb, True, "섹터 분류 미해결 — 시총 상위로 대체 선정")

    # 1) KRX OpenAPI (포털 승인 필요)
    krx_result = _try_krx_openapi(target_ticker, today_yyyymmdd, n)
    if krx_result is not None:
        peers, note = krx_result
        return PeerSelection(peers=peers, degraded=bool(note), note=note)

    # 2) DART induty_code 매칭
    dart_result = _try_dart_induty(target_ticker, today_yyyymmdd, n)
    if dart_result is not None:
        peers, note = dart_result
        return PeerSelection(peers=peers, degraded=False, note=note)

    # 3) pykrx 시총 상위 (섹터 무관 — degraded)
    peers, degraded, note = _try_pykrx(target_ticker, sector_code, today_yyyymmdd, n)
    return PeerSelection(peers=peers, degraded=degraded, note=note)


def validate_override(override: list[str], target_ticker: str) -> list[str]:
    """CLI ``--peers`` 입력 검증."""
    out: list[str] = []
    for p in override:
        if p == target_ticker:
            continue
        if p in out:
            continue
        out.append(p)
    return out
