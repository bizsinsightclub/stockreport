"""재무제표 정규화 — 분기별 매출/영업이익/순이익."""

from __future__ import annotations

from typing import Any

import pandas as pd


def normalize(financial_records: list[dict[str, Any]] | dict[str, Any]) -> pd.DataFrame:
    """다양한 입력 형태를 통일된 DataFrame 으로.

    입력 가능 형태:
      - ``[{"period": "2024Q1", "매출액": ..., "영업이익": ..., "순이익": ...}, ...]``
      - ``{"quarters": [...], "revenue": [...], "op_income": [...], "net_income": [...]}``

    출력 컬럼: period, 매출액, 영업이익, 순이익
    """
    if not financial_records:
        return pd.DataFrame(columns=["period", "매출액", "영업이익", "순이익"])

    if isinstance(financial_records, dict):
        quarters = financial_records.get("quarters") or financial_records.get("periods") or []
        rows = []
        for i, q in enumerate(quarters):
            rows.append(
                {
                    "period": q,
                    "매출액": _safe_get_idx(financial_records.get("revenue") or financial_records.get("매출액"), i),
                    "영업이익": _safe_get_idx(financial_records.get("op_income") or financial_records.get("영업이익"), i),
                    "순이익": _safe_get_idx(financial_records.get("net_income") or financial_records.get("순이익"), i),
                }
            )
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(financial_records)

    # 컬럼 정규화
    rename: dict[str, str] = {}
    for c in df.columns:
        lower = str(c).lower()
        if c in ("매출액", "영업이익", "순이익", "period"):
            continue
        if lower in ("revenue", "sales"):
            rename[c] = "매출액"
        elif lower in ("op_income", "operating_income", "영업이익"):
            rename[c] = "영업이익"
        elif lower in ("net_income", "profit"):
            rename[c] = "순이익"
        elif lower in ("period", "quarter"):
            rename[c] = "period"
    if rename:
        df = df.rename(columns=rename)

    for col in ("매출액", "영업이익", "순이익"):
        if col not in df.columns:
            df[col] = None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "period" not in df.columns:
        df["period"] = [f"Q{i+1}" for i in range(len(df))]

    return df[["period", "매출액", "영업이익", "순이익"]]


def _safe_get_idx(seq: Any, i: int) -> Any:
    if seq is None:
        return None
    try:
        return seq[i]
    except (IndexError, KeyError, TypeError):
        return None


# ─── valuation 지표 ──────────────────────────────────────────────────


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


def _period_sort_key(k: str) -> tuple[int, int]:
    """(year, q) — Q1<Q2<Q3<FY 순서. ``2024-FY`` → (2024, 4)."""
    try:
        year_part, suffix = k.split("-", 1)
        year = int(year_part)
    except ValueError:
        return (0, 0)
    if suffix.startswith("Q"):
        try:
            return (year, int(suffix[1:]))
        except ValueError:
            return (year, 0)
    if suffix == "FY":
        return (year, 4)
    return (year, 0)


# DART account_nm → 정규화된 키
_BS_ACCOUNT_MAP = {
    "자본총계": "equity",
    "부채총계": "liabilities",
    "자산총계": "assets",
}

_NETINCOME_NAMES = frozenset(
    {
        "당기순이익",
        "당기순이익(손실)",
        "분기순이익",
        "분기순이익(손실)",
        "반기순이익",
        "반기순이익(손실)",
    }
)


def valuation_metrics(
    financial_records: list[dict[str, Any]] | None,
    market_fundamental: dict[str, Any] | None,
) -> dict[str, Any]:
    """재무 valuation 6 지표.

    - PER / PBR / EPS / BPS: pykrx ``market_fundamental`` 그대로 (시장 반영 시점)
    - ROE: DART 가장 최근 (FY 우선) 순이익 / 자본총계 × 100
    - 부채비율: DART 가장 최근 부채총계 / 자본총계 × 100

    적자/0 값은 None 으로 표기 (UI 에서 N/A).
    """
    out: dict[str, Any] = {
        "per": None,
        "pbr": None,
        "eps": None,
        "bps": None,
        "roe": None,
        "debt_ratio": None,
        "as_of_period": None,  # ROE/부채비율 기준 보고기간
    }

    # (1) 시장 지표 — pykrx
    if market_fundamental:
        per = _to_float(market_fundamental.get("PER"))
        pbr = _to_float(market_fundamental.get("PBR"))
        eps = _to_float(market_fundamental.get("EPS"))
        bps = _to_float(market_fundamental.get("BPS"))
        out["per"] = per if per and per > 0 else None
        out["pbr"] = pbr if pbr and pbr > 0 else None
        out["eps"] = eps if eps and eps != 0 else None
        out["bps"] = bps if bps and bps > 0 else None

    # (2) DART 보고서에서 ROE / 부채비율
    if financial_records:
        # period 별 BS / 순이익 그룹
        by_period: dict[str, dict[str, Any]] = {}
        for r in financial_records:
            period = str(r.get("_period_key") or "")
            if not period:
                continue
            sj_div = str(r.get("sj_div") or "").upper()
            account = str(r.get("account_nm") or "").strip()
            amount = _to_float(r.get("thstrm_amount"))
            if amount is None:
                continue
            bucket = by_period.setdefault(period, {})
            if sj_div == "BS":
                key = _BS_ACCOUNT_MAP.get(account)
                if key:
                    bucket.setdefault(key, amount)
            elif sj_div in ("CIS", "IS"):
                if account in _NETINCOME_NAMES:
                    bucket.setdefault("net_income", amount)

        # 최신 기간 (FY 우선) 부터 ROE/부채비율 추출
        for period in sorted(by_period.keys(), key=_period_sort_key, reverse=True):
            b = by_period[period]
            equity = b.get("equity")
            liabilities = b.get("liabilities")
            net_income = b.get("net_income")
            if (
                equity
                and equity != 0
                and net_income is not None
                and out["roe"] is None
            ):
                out["roe"] = round(net_income / equity * 100.0, 2)
                out["as_of_period"] = period
            if (
                equity
                and equity != 0
                and liabilities is not None
                and out["debt_ratio"] is None
            ):
                out["debt_ratio"] = round(liabilities / equity * 100.0, 2)
            if out["roe"] is not None and out["debt_ratio"] is not None:
                break

    return out
