"""거시 시리즈 정규화 — USD/KRW 등."""

from __future__ import annotations

from typing import Any

import pandas as pd


def normalize_usdkrw(records: list[dict[str, Any]]) -> pd.DataFrame:
    """USD/KRW 환율 시리즈 → DataFrame(index=date, columns=[종가] or [기준환율])."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    # pykrx 의 환율 컬럼은 "종가" / "기준환율" / "매매기준율" 등 버전마다 다름
    for cand in ("종가", "기준환율", "매매기준율", "close"):
        if cand in df.columns:
            return df[[cand]].rename(columns={cand: "value"})

    # 모르는 컬럼이면 첫 numeric 컬럼만
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            return df[[col]].rename(columns={col: "value"})
    return pd.DataFrame()


def latest_value(df: pd.DataFrame) -> tuple[float | None, float | None]:
    """(현재값, 5일 변화율 %)."""
    if df.empty or "value" not in df.columns:
        return None, None
    s = df["value"].astype(float).dropna()
    if s.empty:
        return None, None
    last = float(s.iloc[-1])
    if len(s) >= 6:
        prev = float(s.iloc[-6])
        delta = (last - prev) / prev * 100.0 if prev else 0.0
    else:
        delta = 0.0
    return last, round(delta, 2)


def fallback_s4_macro(name: str, df: pd.DataFrame) -> str:
    last, delta = latest_value(df)
    if last is None:
        return f"{name} 시리즈를 수집하지 못했습니다."
    return f"{name} {last:,.2f} ({delta:+.2f}%, 5거래일)"
