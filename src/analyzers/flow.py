"""외국인/기관/개인 수급 분석."""

from __future__ import annotations

from typing import Any

import pandas as pd

_INVESTOR_COLS = [
    "외국인", "기관", "개인",
    "기관계", "외국인계",
    "기관합계", "외국인합계", "기타법인",
]
_FOREIGN_COL_PRIORITY = ("외국인합계", "외국인계", "외국인")


def _to_df(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    return df


def enrich(flow_records: list[dict[str, Any]]) -> pd.DataFrame:
    """외/기/개 누적 순매수 (KRW)."""
    df = _to_df(flow_records)
    if df.empty:
        return df

    keep_cols = [c for c in df.columns if c in _INVESTOR_COLS]
    if not keep_cols:
        return df

    cum = df[keep_cols].astype(float).cumsum()
    cum.columns = [f"{c}_누적" for c in keep_cols]
    return pd.concat([df[keep_cols].astype(float), cum], axis=1)


def foreign_net_5d(enriched: pd.DataFrame) -> float | None:
    """외국인 직전 5일 순매수 합계 (단위: KRW)."""
    if enriched.empty:
        return None
    for col in _FOREIGN_COL_PRIORITY:
        if col in enriched.columns:
            tail = enriched[col].astype(float).tail(5)
            if len(tail) == 0:
                return None
            return float(tail.sum())
    return None
