# HANDOFF — KRX 임의 종목 일일 분석 리포트

> **목적**: Claude Code 또는 다른 개발자가 이 프로젝트를 이어받아 작업할 수 있도록 현재까지의 의사결정·진행 상태·다음 작업을 정리한 인수인계서.

작성일: 2026-05-08
Phase 1 완료 시점

---

## 1. 프로젝트 한 줄 요약

임의 KRX 종목(KOSPI/KOSDAQ, 사용자가 ticker 전달)의 시세·수급·공시·재무·피어·거시를 사용자 호출 시점에 수집해 **환각 없는** 정적 HTML 대시보드로 발행한다. cron 미사용, 로컬 CLI/슬래시 커맨드.

## 2. 핵심 의사결정 (변경 시 이 표를 먼저 갱신할 것)

| 항목 | 결정 | 이유 |
|---|---|---|
| 분석 대상 | 사용자 입력 ticker (KRX). 단일 종목당 1개 리포트 | 임의 종목 일반화, 그룹 종합은 추후 옵션 |
| 리포트 섹션 | 시세, 수급, 기술지표, 공시, 재무제표, 피어 비교, 거시 (총 7섹션) | Balanced 범위 — 사용자가 명시 선택 |
| 산출물 | 정적 HTML 대시보드 | 운영 부담 최소 |
| 실행/배포 | 사용자 호출형 CLI/슬래시 커맨드. 정적 파일은 로컬 + 선택적 수동 publish | 노트북 의존성 OK, 사용자 의도에 맞춤 |
| MCP 호출 | Python MCP SDK 직접 호출 (LangChain 미사용) | 경량, LLM 불필요 |
| 데이터 1차 소스 | `korea-stock-mcp` + pykrx fallback | DART + KRX 공식 API 통합 + 키 없이도 동작 |
| LLM 코멘트 | **Phase 1 미사용 / Phase 2 도입 예정** | 사용자가 Phase 1 종료 후 LLM + claim-level citation 도입 결정 |
| 환각 방지 | 3중 안전장치 (메타 트리플 + 규칙 기반 신호 + 사후 숫자 대조) | LLM 미사용에도 운영 시 데이터 출처 추적성 확보 |

## 3. 디렉토리 구조 (현재 상태)

```
reporter/
├── README.md                       ✅
├── HANDOFF.md                      ✅ 본 문서
├── CLAUDE.md                       ✅ Claude Code 운영 규칙
├── requirements.txt                ✅
├── .env.example                    ✅
├── .gitignore                      ✅
├── test_render.py                  ✅ 더미 fixtures 골격 smoke test
├── tests/
│   ├── fixtures/                   ✅ 미니 raw 픽스처 (329180/010140/042660/macro)
│   ├── test_peers.py               ✅
│   └── test_numbers_filter.py      ✅
├── src/
│   ├── config.py                   ✅ 상수 + SECTOR_MACRO_MAP
│   ├── cli.py                      ✅ argparse 진입점
│   ├── main.py                     ✅ 오케스트레이션
│   ├── meta/
│   │   ├── ticker.py               ✅
│   │   └── peers.py                ✅ auto_select + override
│   ├── mcp_clients/
│   │   ├── client.py               ✅
│   │   └── korea_stock.py          ⚠ 도구명 매핑 1차 확인 필요 (§5)
│   ├── collectors/
│   │   ├── krx_openapi.py          ✅
│   │   ├── dart_openapi.py         ✅
│   │   └── macro.py                ✅
│   ├── fallbacks/
│   │   └── pykrx_price.py          ✅
│   ├── analyzers/
│   │   ├── price.py                ✅
│   │   ├── flow.py                 ✅
│   │   ├── disclosure.py           ✅
│   │   ├── financials.py           ✅
│   │   ├── peer.py                 ✅
│   │   └── macro.py                ✅
│   ├── validators/
│   │   └── numbers.py              ✅ v2 (svg/script/data-noverify 제외)
│   └── renderer/
│       ├── charts.py               ✅ _LAYOUT_BASE + 5종 차트
│       ├── html.py                 ✅ render_skeleton + index 갱신
│       └── templates/
│           ├── dashboard.html.j2   ✅ 7섹션 + 6 LLM 슬롯
│           ├── ticker_index.html.j2 ✅
│           └── root_index.html.j2  ✅
└── data/
    ├── raw/{YYYY-MM-DD}/{ticker}_*.json
    └── output/
        ├── {ticker}/{YYYY-MM-DD}.html
        ├── {ticker}/index.html
        └── index.html
```

## 4. 데이터 흐름 (Phase 1)

```
사용자 호출: python -m src.main <ticker> [--peers ...] [--date YYYY-MM-DD] [--skip-llm]
    └─ build(args)
        ├─ meta.ticker.resolve(ticker)              → name, market, sector_code
        ├─ meta.peers.auto_select(sector_code, ...) → [peer1..peerN]  (또는 --peers 오버라이드)
        ├─ collect_all()                            모두 메타 트리플 wrapping
        │   ├─ ks.fetch_stock_price / pykrx fallback   → data/raw/{date}/{ticker}_price.json
        │   ├─ ks.fetch_investor_flow / pykrx          → {ticker}_flow.json
        │   ├─ ks.fetch_disclosure_list (Phase 1: noop) → {ticker}_disclosures.json
        │   ├─ ks.fetch_financials (Phase 1: noop)      → {ticker}_financials.json
        │   ├─ for peer in peers: fetch_stock_price     → {peer}_price.json
        │   └─ macro.fetch_usdkrw + 섹터 매핑           → _macro_*.json
        ├─ analyze()  (analyzers는 mcp_clients/renderer 미import — 순수 함수)
        │   ├─ price.enrich → df + latest_signals (시그널 카드 dict)
        │   ├─ flow.enrich  → 외/기/개 누적 수급 df
        │   ├─ disclosure.classify + 정규식 추출
        │   ├─ financials.normalize → 분기별 매출/영업이익/순이익
        │   ├─ peer.normalized_frame → 6M 정규화 100 기준 df
        │   └─ macro.normalize
        ├─ renderer.html.render_skeleton(ctx)          → data/output/{ticker}/{date}.html (1차, validation 없음)
        ├─ validators.numbers.verify_html_against_raw  → validation dict + .validation.json 사이드카
        ├─ renderer.html.render_skeleton(ctx + val)    → data/output/{ticker}/{date}.html (2차, 검증 배지 포함)
        └─ renderer.html.update_ticker_index + update_root_index
```

cron 자동화 / GitHub Pages 배포는 Phase 1 에서 폐기됐다. Phase 2 슬래시 커맨드 도입 시 다시 검토.

## 5. ⚠ 즉시 확인이 필요한 항목 (Phase 1 → Phase 1.5 인계)

### 5.1 MCP 도구명 실제 검증
`src/mcp_clients/korea_stock.py`의 `_TOOLS` 딕셔너리는 README/사용 예시에서 추정한 이름입니다. 첫 로컬 실행 시 반드시 실제 도구명을 확인하세요.

```bash
# 로컬에서 실행
python -c "
import asyncio
from src.mcp_clients.client import list_available_tools
from src.config import KOREA_STOCK_MCP
import json
print(json.dumps(asyncio.run(list_available_tools(KOREA_STOCK_MCP)), indent=2, ensure_ascii=False))
"
```

확인된 실제 도구명으로 `_TOOLS` dict을 보정한 후, 각 함수의 인자명(`ticker` vs `corp_code`, `start_date` vs `bgn_de` 등)도 함께 맞춰주세요.

### 5.2 KRX API 키 승인 대기
KRX OpenAPI는 신청 후 최대 1일 소요. 그 사이 임시로 `pykrx` 라이브러리(키 불필요)로 시세를 가져오는 백업 collector를 만들 수 있습니다. `src/mcp_clients/` 옆에 `src/fallbacks/pykrx_price.py` 형태로 두고, MCP 호출 실패 시 자동 fallback 하도록 `main.py`에 try/except 추가하면 됩니다.

### 5.3 환각 검증기 노이즈 필터링 (해결됨)
Phase 1 의 `src/validators/numbers.py` v2 가 이 이슈를 해결했다:
- BeautifulSoup 으로 `<script>`, `<style>`, `<svg>` 서브트리 제거
- `data-noverify="true"` 요소(차트 카드, validation 배지 자체) 제거
- 가시 텍스트의 정수/소수/% 토큰만 raw JSON multiset 과 ±0.1% 또는 ±0.5 절대 허용으로 비교
- 결과는 `data/output/{ticker}/{date}.validation.json` 사이드카 + HTML 하단 배지로 표시

테스트는 `tests/test_numbers_filter.py` 참조.

### 5.4 GitHub Actions (Phase 2 이후 재논의)
Phase 1 에서는 cron/Pages 운영이 폐기됐다. 자동 발행이 필요해지면 다음 세션에서 재도입.

## 6. Phase 2 — 다음에 할 일

본 세션은 결정론 코어(Phase 1)만 구현했다. Phase 2 에서는:

1. **슬래시 커맨드** `.claude/commands/report-stock.md` — `/report-stock <ticker>` 진입점.
2. **Claude Code 세션 내부 LLM 코멘트** — `src/llm/` 추가. 슬롯별 (brief, s1_price, s2_tech, s3_disc[i], s4_peer, s4_macro) 텍스트 생성. `data/llm/{ticker}/{date}.json` 으로 캐시.
3. **claim-level citation 검증** — `src/validators/citations.py`. 모든 LLM 문장이 raw JSON 의 출처(source URL/도구명, 조회시각)에 anchor 되어 있는지 체크. 실패 슬롯은 fallback 텍스트로 자동 강등.
4. **CLAUDE.md §0.3 / §3.3 갱신** — "LLM 미사용" 표현을 "claim-level citation 의무화" 로 교체.

### 6.x Phase 3 옵션 (선택)
- 이벤트 스터디 (수주공시 ±5일 CAR)
- 컨센서스 스크래핑 (네이버 금융)
- 알림 (Slack/이메일)
- 백테스팅 백엔드

## 7. 알려진 제약·이슈

| 이슈 | 영향 | 우회/해결 |
|---|---|---|
| KRX 승인 1일 대기 | 첫 빌드 지연 | pykrx 백업 collector |
| `korea-stock-mcp`은 stdio MCP | claude.ai 웹/모바일에서 직접 호출 불가 | Python SDK로 서브프로세스 spawn (현재 방식) |
| Plotly CDN 의존 | 오프라인 환경에서 차트 미표시 | `include_plotlyjs=True`로 인라인 |
| GitHub Actions 무료 한도 | private repo는 월 2,000분 제한 | public repo 또는 self-hosted runner |
| 한글 폰트 | GitHub Pages는 Google Fonts 직접 로드 (CORS OK) | OK, 별도 처리 불필요 |
| MCP 첫 호출 npx 다운로드 | 매번 1-2분 소요 | Actions cache 또는 글로벌 install로 단축 가능 |

## 8. 테스트 방법

### 로컬 더미 데이터 렌더링 (API 키 없이)
```bash
python test_render.py
open data/output/$(date +%Y-%m-%d).html
```

### 로컬 실 데이터 빌드
```bash
cp .env.example .env  # API 키 입력
python -m src.main
```

### MCP 도구 목록 확인
§5.1 참조

## 9. 의사결정 변경이 필요한 신호

다음 상황에서는 §2 표를 다시 검토해야 합니다:

- 사용자가 "AI 에이전트가 대신 분석" 방향으로 선회 → **이미 Phase 2 가 그 방향이다**. 본 항목은 Phase 2 에서 자연스럽게 흡수됨.
- 분석 대상 종목 다수화 요청 → `TARGET`을 리스트로 변환, 리포트 인덱스 페이지 추가
- 인터랙티브(필터링·드릴다운) 요구 → 정적 HTML에서 Streamlit/Dash로 전환
- 실시간 (장중) 갱신 요구 → cron 빈도 증가 또는 webhook 기반으로 전환

## 10. 사용자 컨텍스트

- 코딩 경험은 있으나 본업은 비개발 (업무 생산성 향상 목적의 자동화 선호)
- 결과물의 **추적성·재현성·환각 방지**를 강하게 요구함
- 한국어로 소통, 숫자는 천단위 콤마, 등락 색상은 한국 관습(상승=빨강, 하락=파랑)
- 매일 받아보고 싶다는 의도 → 자동화 우선

## 11. 외부 참조

- korea-stock-mcp: https://github.com/jjlabsio/korea-stock-mcp
- DART OpenAPI: https://opendart.fss.or.kr
- KRX OpenAPI: https://openapi.krx.co.kr
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Plotly Python: https://plotly.com/python/
