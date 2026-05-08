# 종목 리포트 분석기 (Phase 1)

KRX(KOSPI/KOSDAQ) 임의 종목에 대해 결정론 기반 일일 분석 리포트(정적 HTML)를 생성한다. LLM 미사용.

```bash
python -m src.main 329180                       # HD현대중공업
python -m src.main 005930 --peers 000660,066570 # 삼성전자 + 피어 오버라이드
python -m src.main 035720 --date 2026-05-09     # 카카오, 특정 날짜로 발행
```

산출물: `data/output/{ticker}/{YYYY-MM-DD}.html` + ticker별 index + 루트 index. raw JSON 스냅샷은 `data/raw/{YYYY-MM-DD}/{ticker}_*.json`에 메타 트리플 형식으로 보존.

## Requirements

- **Python 3.11+** (PEP 604 union 문법 `X | Y` 사용. 3.10 미만에서는 동작하지 않음)
- 의존성은 `requirements.txt` 참고. `pip install -r requirements.txt`

API 키 없이도 `pykrx` fallback으로 동작한다. DART 공시 카테고리/원문 링크는 `DART_API_KEY` 가 필요.

## 데이터 소스

| 영역 | 1차 소스 | Fallback |
|---|---|---|
| 시세·OHLCV | `korea-stock-mcp:get_stock_price` | `pykrx.get_market_ohlcv_by_date` |
| 외/기/개 수급 | `korea-stock-mcp:get_investor_flow` | `pykrx.get_market_trading_value_by_investor` |
| 공시 | `korea-stock-mcp:get_disclosure_list` 또는 DART OpenAPI | (없음 — silent skip) |
| 재무제표 | `korea-stock-mcp:get_financials` 또는 DART XBRL | (없음 — silent skip) |
| 시가총액 랭킹 | KRX OpenAPI | `pykrx.get_market_cap_by_ticker` |
| USD/KRW 거시 | `pykrx.get_exhange_rate_by_date` 또는 ECOS | (없음) |

## 환각 방지

CLAUDE.md §3에 정의된 메타 트리플 wrapping을 모든 fetch 함수에서 강제한다. 빌드 후 `validators/numbers.py` 가 HTML 내 모든 가시 숫자(콤마/소수점/`%` 토큰)를 raw JSON multiset과 대조하고, 결과 배지를 HTML 하단에 표시한다. SVG/script/style/`data-noverify="true"` 영역은 검증 대상에서 제외된다.

## Phase 1 assumptions

- `korea-stock-mcp`의 도구 이름은 `_TOOLS` dict에 추정으로 박혀있음 (`get_stock_price`, `get_disclosure_list`, `get_financials`, `get_investor_flow`). 실제 환경에서 다르면 `src/mcp_clients/korea_stock.py` 의 `_TOOLS` 딕셔너리만 보정. `python -m src.mcp_clients.client --list` 로 확인 가능.
- RSI 과매수/과매도 임계치: 70 / 30 (시장 관행). `src/config.py`의 `RSI_OVERBOUGHT`, `RSI_OVERSOLD` 상수.
- 피어 자동 선정 N=5. `--peers` 명시 시 오버라이드.
- `SECTOR_MACRO_MAP` 초기값은 조선/반도체/자동차 3개. 그 외 업종은 `DEFAULT_MACRO=["USDKRW"]` 만.
- 섹터 분류 lookup이 실패하면 시총 상위 N개로 degrade하고 검증 배지에 노트 표기.
- LLM 슬롯은 6개 정의 (brief, s1_price, s2_tech, s3_disc[i], s4_peer, s4_macro). Phase 1 에서는 룰 기반 fallback 문장으로 채우고, Phase 2 에서 LLM 텍스트로 교체.
- `test_render.py` 는 5행짜리 미니 fixture로 동작하므로 검증 배지가 ~40% unmatched (`fail`) 로 뜨는 것이 **정상**이다. 실 데이터 빌드 (`python -m src.main <ticker>`) 의 목표 unmatched 는 <5%.

## Phase 2 (별도 세션)

- 슬래시 커맨드 `/report-stock <ticker>`
- Claude Code 세션 내부 LLM 코멘트 + claim-level citation 검증기
- `.claude/commands/report-stock.md`, `src/llm/`, `src/validators/citations.py`

## 디렉토리

```
src/
├── config.py              상수 (PEER_N, lookback, design tokens, SECTOR_MACRO_MAP)
├── cli.py                 argparse 진입점
├── main.py                오케스트레이션
├── meta/
│   ├── ticker.py          ticker → name/market/sector
│   └── peers.py           auto_select 피어 선정
├── mcp_clients/           외부 MCP 호출 (메타 트리플 반환)
├── collectors/            공식 OpenAPI HTTP 수집
├── fallbacks/             pykrx 백업
├── analyzers/             순수 함수 (외부 호출 금지)
├── validators/            HTML↔raw 숫자 검증
└── renderer/              Plotly 차트 + Jinja2 템플릿
```

자세한 운영 규칙은 `CLAUDE.md`, 인계 컨텍스트는 `HANDOFF.md` 참조.
