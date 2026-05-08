"""기술지표 계산 — MA / RSI / MACD / Bollinger / 52w hi-lo."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    BOLLINGER_PERIOD,
    BOLLINGER_STD,
    MA_LONG,
    MA_MID,
    MA_SHORT,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    WEEK_52_DAYS,
)

logger = logging.getLogger(__name__)


def _records_to_df(records: list[dict[str, Any]]) -> pd.DataFrame:
    """meta-triple 의 ``data`` 리스트(dict) → DataFrame (index=date)."""
    if not records:
        return pd.DataFrame(
            columns=["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률"]
        )
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    return df


def _close_col(df: pd.DataFrame) -> str:
    for cand in ("종가", "close", "Close"):
        if cand in df.columns:
            return cand
    raise KeyError("종가 컬럼을 찾을 수 없습니다")


def enrich(price_records: list[dict[str, Any]]) -> pd.DataFrame:
    """OHLCV records → 기술지표 컬럼이 추가된 DataFrame."""
    df = _records_to_df(price_records)
    if df.empty:
        return df
    close_col = _close_col(df)
    close = df[close_col].astype(float)

    df["MA5"] = close.rolling(MA_SHORT).mean()
    df["MA20"] = close.rolling(MA_MID).mean()
    df["MA60"] = close.rolling(MA_LONG).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    bb_mid = close.rolling(BOLLINGER_PERIOD).mean()
    bb_std = close.rolling(BOLLINGER_PERIOD).std()
    df["BB_mid"] = bb_mid
    df["BB_upper"] = bb_mid + BOLLINGER_STD * bb_std
    df["BB_lower"] = bb_mid - BOLLINGER_STD * bb_std

    return df


def latest_signals(enriched: pd.DataFrame) -> dict[str, Any]:
    """signal card 용 dict.

    반환 키: trend_ma, rsi, rsi_label, macd_dir, bollinger, week52_pos.
    """
    if enriched.empty:
        return {
            "trend_ma": "—",
            "rsi": None,
            "rsi_label": "—",
            "macd_dir": "—",
            "bollinger": "—",
            "week52_pos": None,
        }

    last = enriched.iloc[-1]
    close_col = _close_col(enriched)
    close_now = float(last[close_col])

    # MA trend (golden/dead)
    ma5 = last.get("MA5")
    ma20 = last.get("MA20")
    if pd.notna(ma5) and pd.notna(ma20):
        trend = "골든" if ma5 > ma20 else ("데드" if ma5 < ma20 else "중립")
    else:
        trend = "—"

    rsi = last.get("RSI")
    rsi_value: float | None = float(rsi) if pd.notna(rsi) else None
    if rsi_value is None:
        rsi_label = "—"
    elif rsi_value >= RSI_OVERBOUGHT:
        rsi_label = "과매수권"
    elif rsi_value <= RSI_OVERSOLD:
        rsi_label = "과매도권"
    else:
        rsi_label = "중립권"

    macd_hist = last.get("MACD_hist")
    if pd.notna(macd_hist):
        macd_dir = "상승" if macd_hist > 0 else "하락"
    else:
        macd_dir = "—"

    bb_upper = last.get("BB_upper")
    bb_lower = last.get("BB_lower")
    if pd.notna(bb_upper) and close_now > bb_upper:
        bb_label = "상단 돌파"
    elif pd.notna(bb_lower) and close_now < bb_lower:
        bb_label = "하단 이탈"
    else:
        bb_label = "밴드 내"

    # 52w high/low position (% of range)
    tail = enriched.tail(WEEK_52_DAYS)
    week52_pos: float | None = None
    if not tail.empty:
        hi = float(tail[close_col].max())
        lo = float(tail[close_col].min())
        if hi > lo:
            week52_pos = round((close_now - lo) / (hi - lo) * 100.0, 1)

    return {
        "trend_ma": trend,
        "rsi": round(rsi_value, 1) if rsi_value is not None else None,
        "rsi_label": rsi_label,
        "macd_dir": macd_dir,
        "bollinger": bb_label,
        "week52_pos": week52_pos,
        "close_now": round(close_now),
    }


def header_summary(enriched: pd.DataFrame) -> dict[str, Any]:
    """헤더 가격/등락률."""
    if enriched.empty:
        return {"price_now": None, "change_pct": None, "as_of": None, "direction": "flat"}
    close_col = _close_col(enriched)
    last = enriched.iloc[-1]
    price_now = float(last[close_col])
    if len(enriched) >= 2:
        prev = float(enriched.iloc[-2][close_col])
        change_pct = (price_now - prev) / prev * 100.0 if prev else 0.0
    else:
        change_pct = 0.0
    as_of = enriched.index[-1].strftime("%Y-%m-%d") if hasattr(enriched.index[-1], "strftime") else str(enriched.index[-1])
    direction = "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat")
    return {
        "price_now": round(price_now),
        "change_pct": round(change_pct, 2),
        "as_of": as_of,
        "direction": direction,
    }


def fallback_brief(enriched: pd.DataFrame, ticker: str) -> str:
    """LLM 미사용 시 ``brief`` 슬롯에 채울 룰 기반 한 줄."""
    if enriched.empty:
        return f"{ticker} 시세 데이터를 수집하지 못했습니다."
    close_col = _close_col(enriched)
    closes = enriched[close_col].astype(float)
    last = float(closes.iloc[-1])
    if len(closes) >= 6:
        prev = float(closes.iloc[-6])
        delta = (last - prev) / prev * 100.0 if prev else 0.0
        return f"최근 5거래일 종가는 {delta:+.2f}% 변화했습니다."
    return f"수집된 거래일 수가 부족합니다 ({len(closes)} 일)."


def fallback_s1_price(enriched: pd.DataFrame) -> str:
    """§1 (시세·거래대금) 슬롯 fallback."""
    if enriched.empty or "거래대금" not in enriched.columns:
        return "거래대금 시리즈를 확인할 수 없습니다."
    val = enriched["거래대금"].astype(float)
    if len(val) < 60:
        return f"거래대금 표본이 부족합니다 ({len(val)} 일)."
    last = float(val.iloc[-1])
    avg60 = float(val.tail(60).mean())
    if avg60 == 0:
        return "거래대금 60일 평균이 0입니다."
    ratio = (last - avg60) / avg60 * 100.0
    return f"최근 거래대금은 60일 평균 대비 {ratio:+.1f}% 입니다."


def fallback_s2_tech(signals: dict[str, Any]) -> str:
    rsi = signals.get("rsi")
    label = signals.get("rsi_label", "—")
    macd = signals.get("macd_dir", "—")
    if rsi is None:
        return f"기술지표 산출이 불완전합니다 (MACD: {macd})."
    return f"RSI(14) {rsi}, {label}. MACD 방향성 {macd}."
