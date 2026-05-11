"""상수만 정의. 비즈니스 로직 두지 말 것 (CLAUDE.md §2)."""

from __future__ import annotations

from pathlib import Path

# ─── 경로 ────────────────────────────────────────────────────────────
ROOT_DIR: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
OUTPUT_DIR: Path = DATA_DIR / "output"
LLM_DIR: Path = DATA_DIR / "llm"  # Phase 2 — LLM 사이드카
TEMPLATE_DIR: Path = Path(__file__).resolve().parent / "renderer" / "templates"

# ─── 분석 설정 ────────────────────────────────────────────────────────
PEER_N: int = 5
PRICE_LOOKBACK_DAYS: int = 180
DISCLOSURE_LOOKBACK_DAYS: int = 30
PEER_NORMALIZED_LOOKBACK_DAYS: int = 180  # 6 months
MACRO_LOOKBACK_DAYS: int = 180

# KRX OpenAPI ETP(ETF/ETN/ELW) 일별매매 데이터는 당일 야간/T+1 게시 지연이 있어,
# 실매매 데이터가 있는 최근 영업일로 walk-back 한다 (최대 N 영업일 전까지 probe).
MARKET_DATE_WALKBACK_DAYS: int = 7

# ─── 기술지표 임계치 (Phase 1 assumption: 시장 관행) ──────────────────
RSI_PERIOD: int = 14
RSI_OVERBOUGHT: float = 70.0
RSI_OVERSOLD: float = 30.0
MA_SHORT: int = 5
MA_MID: int = 20
MA_LONG: int = 60
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9
BOLLINGER_PERIOD: int = 20
BOLLINGER_STD: float = 2.0
WEEK_52_DAYS: int = 252  # 영업일 1년 ≈ 252

# ─── 디자인 토큰 (CLAUDE.md §6) — charts.py에서 참조 ─────────────────
COLOR_BG: str = "#0f0f10"
COLOR_SURFACE: str = "#16161a"
COLOR_BORDER: str = "#26262b"
COLOR_TEXT: str = "#e8e6e3"
COLOR_MUTED: str = "#7a7a82"
COLOR_UP: str = "#e85d4a"  # 상승 (한국 관습)
COLOR_DOWN: str = "#3a7bd5"
COLOR_ACCENT: str = "#d4a574"
COLOR_ACCENT_SOFT: str = "#9c8cb6"

CHART_FONT_FAMILY: str = "'JetBrains Mono', 'Noto Sans KR', monospace"

# ─── 섹터 → 거시 매핑 (Phase 1 assumption: 3개 섹터만) ───────────────
DEFAULT_MACRO: list[str] = ["USDKRW"]
SECTOR_MACRO_MAP: dict[str, list[str]] = {
    "조선": ["USDKRW", "CLARKSON_NEWBUILD", "PLATE_PRICE"],
    "반도체": ["USDKRW", "DRAM_DXI"],
    "자동차": ["USDKRW", "WTI", "STEEL_HRC"],
}

# ─── MCP 진입점 ──────────────────────────────────────────────────────
# korea-stock-mcp는 Node 패키지. npx로 spawn.
KOREA_STOCK_MCP: dict[str, object] = {
    "command": "npx",
    "args": ["-y", "@jjlabsio/korea-stock-mcp"],
    "env": None,  # 호출부에서 ENV 채우기
}

# ─── 공시 카테고리 정규식 (analyzers/disclosure.py 사용) ─────────────
DISCLOSURE_CATEGORY_RULES: list[tuple[str, str]] = [
    ("수주", r"(공급계약|수주|단일판매|선박건조)"),
    ("실적", r"(분기보고서|반기보고서|사업보고서|영업\(잠정\)|매출액)"),
    ("자기주식", r"(자기주식|자사주)"),
    ("지분", r"(대량보유|주식등의|임원ㆍ주요주주)"),
    ("배당", r"(현금ㆍ?현물?\s*배당|주식배당|배당금)"),
    ("증자", r"(유상증자|무상증자|전환사채|신주인수권)"),
]

# 카테고리별 chip 색상 (UI 일관성)
DISCLOSURE_CATEGORY_COLOR: dict[str, str] = {
    "수주": COLOR_ACCENT,
    "실적": COLOR_UP,
    "자기주식": COLOR_ACCENT_SOFT,
    "지분": COLOR_ACCENT_SOFT,
    "배당": COLOR_ACCENT,
    "증자": COLOR_DOWN,
    "기타": COLOR_MUTED,
}

# ─── 검증 노이즈 필터 ────────────────────────────────────────────────
VALIDATION_TOLERANCE_RATIO: float = 0.001  # ±0.1% 이내면 일치 처리 (반올림 보정)
VALIDATION_UNMATCHED_BUDGET: float = 0.05  # 5% 이상이면 fail 배지

# ─── HTML 푸터 디스클레이머 ─────────────────────────────────────────
DISCLAIMER_KO: str = "본 리포트는 정보 제공 목적이며 투자 조언이 아닙니다."
DISCLAIMER_EN: str = "All numbers are auto-extracted from primary sources."
