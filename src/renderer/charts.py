"""Plotly figure → HTML div 문자열.

모든 helper 는 ``str`` (``<div>...</div>``) 을 반환한다. 호출부는 j2 템플릿에
그대로 ``{{ chart_xxx | safe }}`` 로 박는다.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.config import (
    CHART_FONT_FAMILY,
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_DOWN,
    COLOR_MUTED,
    COLOR_TEXT,
    COLOR_UP,
)

logger = logging.getLogger(__name__)


_LAYOUT_BASE: dict[str, Any] = {
    "paper_bgcolor": COLOR_BG,
    "plot_bgcolor": COLOR_BG,
    "font": {"family": CHART_FONT_FAMILY, "color": COLOR_TEXT, "size": 11},
    "margin": {"l": 40, "r": 20, "t": 40, "b": 30},
    "xaxis": {"gridcolor": "#1f1f22", "zerolinecolor": "#1f1f22"},
    "yaxis": {"gridcolor": "#1f1f22", "zerolinecolor": "#1f1f22"},
    "hoverlabel": {
        "font": {"color": COLOR_TEXT},
        "bgcolor": COLOR_BG,
        "bordercolor": COLOR_ACCENT,
    },
    "legend": {
        "orientation": "h",
        "x": 0,
        "y": 1.12,
        "bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLOR_MUTED, "size": 10},
    },
}


def _to_div(fig: Any) -> str:
    """plotly Figure → HTML div (CDN 의존, include_plotlyjs=False)."""
    try:
        return fig.to_html(
            include_plotlyjs=False,
            full_html=False,
            config={"displayModeBar": False, "responsive": True},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("plotly _to_div 실패: %s", exc)
        return '<div class="chart-empty">차트 렌더 실패</div>'


def _empty(msg: str) -> str:
    return f'<div class="chart-empty" style="padding:24px;color:{COLOR_MUTED};font-style:italic">{msg}</div>'


def price_chart(enriched: pd.DataFrame, *, height: int = 320) -> str:
    """일별 종가 + MA20 + Bollinger band."""
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        return _empty("plotly 미설치")
    if enriched is None or enriched.empty:
        return _empty("시세 데이터 없음")

    close_col = next((c for c in ("종가", "close", "Close") if c in enriched.columns), None)
    if close_col is None:
        return _empty("종가 컬럼 없음")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=enriched.index,
            y=enriched[close_col],
            mode="lines",
            name="종가",
            line={"color": COLOR_ACCENT, "width": 2},
        )
    )
    if "MA20" in enriched.columns:
        fig.add_trace(
            go.Scatter(
                x=enriched.index,
                y=enriched["MA20"],
                mode="lines",
                name="MA20",
                line={"color": COLOR_ACCENT_SOFT, "width": 1, "dash": "dot"},
            )
        )
    if "BB_upper" in enriched.columns and "BB_lower" in enriched.columns:
        fig.add_trace(
            go.Scatter(
                x=enriched.index,
                y=enriched["BB_upper"],
                mode="lines",
                name="BB+",
                line={"color": COLOR_BORDER, "width": 1},
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=enriched.index,
                y=enriched["BB_lower"],
                mode="lines",
                name="BB-",
                line={"color": COLOR_BORDER, "width": 1},
                fill="tonexty",
                fillcolor="rgba(38,38,43,0.35)",
                showlegend=False,
            )
        )

    layout = dict(_LAYOUT_BASE)
    layout["height"] = height
    fig.update_layout(**layout)
    return _to_div(fig)


# pykrx ``get_market_trading_value_by_date`` 컬럼 → 표시 이름 매핑
_FLOW_DISPLAY_NAME = {
    "외국인합계": "외국인",
    "외국인계": "외국인",
    "외국인": "외국인",
    "기관합계": "기관",
    "기관계": "기관",
    "기관": "기관",
    "개인": "개인",
    "기타법인": "기타법인",
}

# 그리는 순서 — 뒤에 그릴수록 위에 올라옴. 외국인을 마지막에 그려 강조.
_FLOW_PLOT_ORDER = ["기타법인", "개인", "기관", "외국인"]

_FLOW_STYLE = {
    "외국인": {"color": COLOR_ACCENT, "width": 2.4},        # warm gold (메인)
    "기관": {"color": COLOR_ACCENT_SOFT, "width": 1.6},     # dusty mauve
    "개인": {"color": COLOR_MUTED, "width": 1.2},
    "기타법인": {"color": "#3a4a5a", "width": 1.0},
}

_KRW_PER_OK = 1e8  # 1억 원


def flow_chart(flow_enriched: pd.DataFrame, *, height: int = 260) -> str:
    """외/기/개 누적 순매수 (억원). 외국인 라인을 메인으로 강조."""
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        return _empty("plotly 미설치")
    if flow_enriched is None or flow_enriched.empty:
        return _empty("수급 데이터 없음")

    # display_name → DataFrame 컬럼 매핑 (raw 합계 컬럼 우선)
    display_to_col: dict[str, str] = {}
    for col in flow_enriched.columns:
        if not col.endswith("_누적"):
            continue
        raw_base = col.replace("_누적", "")
        disp = _FLOW_DISPLAY_NAME.get(raw_base, raw_base)
        # ``외국인합계`` 가 ``외국인`` 보다 우선 (pykrx 의 진짜 합계).
        if disp not in display_to_col or raw_base.endswith("합계"):
            display_to_col[disp] = col

    fig = go.Figure()
    for disp in _FLOW_PLOT_ORDER:
        col = display_to_col.get(disp)
        if col is None:
            continue
        style = _FLOW_STYLE.get(disp, {"color": COLOR_TEXT, "width": 1.2})
        y_oku = flow_enriched[col].astype(float) / _KRW_PER_OK
        fig.add_trace(
            go.Scatter(
                x=flow_enriched.index,
                y=y_oku,
                mode="lines",
                name=disp,
                line={"color": style["color"], "width": style["width"]},
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:+,.0f} 억원<extra>" + disp + "</extra>",
            )
        )

    layout = dict(_LAYOUT_BASE)
    layout["height"] = height
    layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "누적 순매수 (억원)", "font": {"color": COLOR_MUTED, "size": 10}}}
    fig.update_layout(**layout)
    return _to_div(fig)


def peer_normalized_chart(normalized: pd.DataFrame, target_ticker: str, *, height: int = 280) -> str:
    """피어 정규화 100 기준 추이."""
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        return _empty("plotly 미설치")
    if normalized is None or normalized.empty:
        return _empty("피어 정규화 시리즈 없음")

    fig = go.Figure()
    palette = [COLOR_ACCENT_SOFT, COLOR_MUTED, "#5a6470", "#8a7a5a", "#6a4a4a"]
    palette_idx = 0
    for col in normalized.columns:
        if col == target_ticker:
            color = COLOR_ACCENT
            width = 2
        else:
            color = palette[palette_idx % len(palette)]
            palette_idx += 1
            width = 1
        fig.add_trace(
            go.Scatter(
                x=normalized.index,
                y=normalized[col],
                mode="lines",
                name=str(col),
                line={"color": color, "width": width},
            )
        )

    layout = dict(_LAYOUT_BASE)
    layout["height"] = height
    fig.update_layout(**layout)
    return _to_div(fig)


_KRW_PER_OK = 1e8  # 1억원
_FINANCIALS_DECIMALS = 2


def _short_period_label(period: str) -> str:
    """``2024-FY`` → ``24 FY``, ``2025-Q1`` → ``25 1Q``."""
    s = str(period).strip()
    if "-" not in s:
        return s
    year_part, suffix = s.split("-", 1)
    year_short = year_part[-2:] if len(year_part) >= 2 else year_part
    if suffix.upper() == "FY":
        return f"{year_short} FY"
    if suffix.upper().startswith("Q"):
        try:
            q = int(suffix[1:])
            return f"{year_short} {q}Q"
        except ValueError:
            return f"{year_short} {suffix}"
    return f"{year_short} {suffix}"


def financials_bars(df: pd.DataFrame, *, height: int = 320) -> str:
    """분기별 매출/영업이익/순이익 막대 — 억원 단위, 소수점 둘째자리.

    바 위에 값을 직접 표시하고 x축은 ``25 1Q`` 형태의 짧은 라벨.
    """
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        return _empty("plotly 미설치")
    if df is None or df.empty:
        return _empty("재무제표 데이터 없음")

    periods = [_short_period_label(p) for p in df["period"]]
    color_map = {"매출액": COLOR_ACCENT, "영업이익": COLOR_ACCENT_SOFT, "순이익": COLOR_MUTED}

    fig = go.Figure()
    for col in ("매출액", "영업이익", "순이익"):
        if col not in df.columns:
            continue
        values_oku = (df[col].astype(float) / _KRW_PER_OK).round(_FINANCIALS_DECIMALS)
        text_labels = [
            f"{v:,.{_FINANCIALS_DECIMALS}f}" if pd.notna(v) else ""
            for v in values_oku
        ]
        fig.add_trace(
            go.Bar(
                x=periods,
                y=values_oku,
                name=col,
                marker={"color": color_map[col]},
                text=text_labels,
                textposition="outside",
                textfont={"family": CHART_FONT_FAMILY, "size": 10, "color": COLOR_TEXT},
                hovertemplate=(
                    "<b>%{x}</b><br>" + col + ": %{y:,.2f} 억원<extra></extra>"
                ),
                cliponaxis=False,
            )
        )

    layout = dict(_LAYOUT_BASE)
    layout["height"] = height
    layout["barmode"] = "group"
    layout["bargap"] = 0.25
    layout["bargroupgap"] = 0.08
    layout["margin"] = {"l": 60, "r": 20, "t": 50, "b": 40}
    layout["yaxis"] = dict(_LAYOUT_BASE["yaxis"])
    layout["yaxis"].update(
        {
            "title": {"text": "억원", "font": {"color": COLOR_MUTED, "size": 10}},
            "tickformat": ",.0f",
            "rangemode": "tozero",
        }
    )
    layout["xaxis"] = dict(_LAYOUT_BASE["xaxis"])
    layout["xaxis"].update({"tickangle": 0})
    fig.update_layout(**layout)
    return _to_div(fig)


def macro_chart(name: str, df: pd.DataFrame, *, height: int = 220) -> str:
    """단일 거시 시리즈."""
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        return _empty("plotly 미설치")
    if df is None or df.empty or "value" not in df.columns:
        return _empty(f"{name} 시리즈 없음")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["value"],
            mode="lines",
            name=name,
            line={"color": COLOR_DOWN, "width": 1.5},
        )
    )
    layout = dict(_LAYOUT_BASE)
    layout["height"] = height
    fig.update_layout(**layout)
    return _to_div(fig)
