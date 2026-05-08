"""피어 비교 — 정규화 100 기준 6개월 추이 + valuation row."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _records_to_close_series(records: list[dict[str, Any]]) -> pd.Series:
    if not records:
        return pd.Series(dtype=float)
    df = pd.DataFrame(records)
    if "date" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    for col in ("종가", "close", "Close"):
        if col in df.columns:
            return df[col].astype(float)
    return pd.Series(dtype=float)


def normalized_frame(
    target_ticker: str,
    target_records: list[dict[str, Any]],
    peers: dict[str, list[dict[str, Any]]],
    *,
    lookback_days: int,
) -> pd.DataFrame:
    """target + peer 시세를 정규화 100 기준으로 묶은 DataFrame.

    columns = [target_ticker, peer1, peer2, ...]
    """
    series_map: dict[str, pd.Series] = {}

    target_s = _records_to_close_series(target_records).tail(lookback_days)
    if not target_s.empty:
        base = float(target_s.iloc[0])
        if base > 0:
            series_map[target_ticker] = target_s / base * 100.0

    for tk, recs in peers.items():
        s = _records_to_close_series(recs).tail(lookback_days)
        if s.empty:
            continue
        base = float(s.iloc[0])
        if base <= 0:
            continue
        series_map[tk] = s / base * 100.0

    if not series_map:
        return pd.DataFrame()
    return pd.DataFrame(series_map).sort_index()


def valuation_row(ticker: str, name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """피어 테이블 한 행 생성. 컬럼: name, ticker, close, change_pct, volume."""
    if not records:
        return {
            "name": name,
            "ticker": ticker,
            "close": None,
            "change_pct": None,
            "volume": None,
            "direction": "flat",
        }
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    close_col = next((c for c in ("종가", "close", "Close") if c in df.columns), None)
    vol_col = next((c for c in ("거래량", "volume", "Volume") if c in df.columns), None)
    if close_col is None:
        return {
            "name": name,
            "ticker": ticker,
            "close": None,
            "change_pct": None,
            "volume": None,
            "direction": "flat",
        }

    last = float(df[close_col].iloc[-1])
    if len(df) >= 2:
        prev = float(df[close_col].iloc[-2])
        change_pct = (last - prev) / prev * 100.0 if prev else 0.0
    else:
        change_pct = 0.0

    volume = float(df[vol_col].iloc[-1]) if vol_col is not None else None

    return {
        "name": name,
        "ticker": ticker,
        "close": round(last),
        "change_pct": round(change_pct, 2),
        "volume": int(volume) if volume is not None else None,
        "direction": "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat"),
    }


def fallback_s4_peer(
    target_ticker: str, normalized: pd.DataFrame
) -> str:
    if normalized.empty or target_ticker not in normalized.columns:
        return "피어 정규화 시리즈를 산출하지 못했습니다."
    last = normalized.iloc[-1]
    target_v = float(last[target_ticker])
    others = [v for k, v in last.items() if k != target_ticker]
    if not others:
        return f"{target_ticker} 6M 정규화 수익률 {target_v - 100:+.1f}%."
    avg = sum(others) / len(others)
    return (
        f"{target_ticker} 6M 정규화 {target_v - 100:+.1f}%, "
        f"피어 평균 {avg - 100:+.1f}% (차이 {target_v - avg:+.1f}p)."
    )
