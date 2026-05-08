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
