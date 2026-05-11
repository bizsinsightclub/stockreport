# CLAUDE.md

> 이 문서는 Claude Code(또는 다른 AI 코딩 어시스턴트)가 이 프로젝트에서 일관되게 따라야 할 **운영 규칙·아키텍처 원칙·코딩 컨벤션**을 정의합니다. 새 작업을 시작하기 전 항상 이 파일을 먼저 읽으세요.

---

## 0. 가장 중요한 원칙 (Top Rules)

1. **환각 없는 분석 (No Hallucination)이 본 프로젝트의 존재 이유다.** 이 원칙을 위반할 가능성이 있는 변경은 거부하거나, 거부하지 못한다면 명시적 경고와 함께 진행하라.
2. **모든 수치는 출처가 있어야 한다.** 코드 어디서든 숫자를 보여주려면 `(값, 출처 URL/도구명, 조회시각)` 메타데이터가 함께 흘러야 한다.
3. **LLM 코멘트는 슬롯에만 사용하며 모든 numeric claim 에 citation 의무.** Phase 2 진입(2026-05-09)으로 LLM 코멘트가 도입되었다. 단 다음 제약을 절대 어기지 마라:
   - LLM 출력은 `data/llm/{ticker}/{date}.json` 사이드카에서만 inject 한다 (외부 API 자동 호출 금지 — Claude Code 세션이 직접 작성).
   - 모든 numeric claim 은 `<span data-cite="file:json-path:value">` 로 wrap 되어야 한다.
   - `validators/citations.py` 가 모든 data-cite 를 raw_dir 안 json path 로 따라가서 value 일치 확인. mismatch 비율 >5% 면 빌드 배지 fail.
   - 정성적 표현(예: "강세권에 진입") 은 자유, 그러나 수치는 반드시 raw 출처 매칭.
4. **재현성이 성능보다 우선한다.** 매 빌드의 raw JSON 스냅샷을 `data/raw/YYYY-MM-DD/`에 보존하는 것은 비용이 들어도 유지하라.
5. **읽기 전에 먼저 읽어라.** 파일 수정 전 반드시 view, MCP 도구 호출 전 반드시 list_tools, 의존성 추가 전 반드시 requirements.txt 확인.

## 1. 프로젝트 한 줄 정의

KOSPI/KOSDAQ 임의 종목에 대해 슬래시 커맨드 `/report-stock <ticker>`(또는 `python -m src.main <ticker>`)로 발행하는 정적 HTML 분석. Phase 1(결정론 코어) + Phase 2(Claude Code 세션 LLM 코멘트 + claim-level citation 검증) 모두 구현됨 (2026-05-09). 매시간 자동 빌드는 로컬 Windows 작업 스케줄러(§7).

상세 컨텍스트와 진행 상황은 **HANDOFF.md** 참조.

## 2. 디렉토리·모듈 책임 (수정 시 이 매핑 유지)

```
src/
├── config.py              상수만 — PEER_N, lookback, design tokens, SECTOR_MACRO_MAP, MCP launch cmd
├── cli.py                 argparse 진입점
├── main.py                오케스트레이션 — 비즈니스 로직 두지 말 것
├── meta/                  종목 메타 정보 + 피어 선정
│   ├── ticker.py          ticker → name/market/sector_code (pykrx)
│   └── peers.py           auto_select(sector_code, n, exclude) + override
├── mcp_clients/           외부 데이터 진입점 (MCP 호출 전담)
│   ├── client.py          MCP stdio 세션 헬퍼 — 도메인 무관
│   └── korea_stock.py     korea-stock-mcp 도메인 래퍼 — 모든 fetch_*는 여기
├── collectors/            공식 OpenAPI 직접 호출 (KRX/DART/macro)
├── fallbacks/             pykrx 백업 collector
├── analyzers/             순수 함수, 외부 호출 없음 — 입력 dict/df → 출력 dict/df
│   ├── price.py           기술지표 계산
│   ├── flow.py            외/기/개 누적 수급
│   ├── disclosure.py      공시 분류 + 계약금액/상대방 정규식
│   ├── financials.py      분기별 매출/영업이익/순이익 정규화
│   ├── peer.py            정규화 100 기준 6M 추이 + valuation row
│   └── macro.py           거시 시리즈 정규화
├── validators/            검증 로직 (실패해도 빌드 성공, 보고만)
│   ├── numbers.py         HTML ↔ raw 숫자 대조 (svg/script/data-noverify 제외)
│   └── citations.py       LLM 슬롯 내 <span data-cite> 가 raw 출처 일치하는지 (Phase 2)
├── llm/                   LLM 사이드카 → 슬롯 inject (Phase 2)
│   └── inject.py          data/llm/{ticker}/{date}.json 읽어 슬롯 wrap, citation 적용
└── renderer/              presentation 레이어 (analyzer 결과 → HTML)
    ├── charts.py          Plotly figure → HTML div
    ├── html.py            Jinja2 환경 + render_skeleton + index 갱신 + render_market_archive (ETP 인터랙티브 대시보드 data/output/market/{date}.html)
    └── templates/         Jinja2 템플릿:
        ├── dashboard.html.j2        종목 일일 리포트
        ├── ticker_index.html.j2     종목별 발행 목록
        ├── root_index.html.j2       루트 인덱스 (시장 요약 + 인사이트 5 + 종목 목록 + 아카이브 링크)
        ├── market_dashboard.html.j2 ETP 인터랙티브 대시보드 (탭 + 정렬/필터/검색, 클라이언트 vanilla JS)
        └── _etp_styles.html.j2      디자인 토큰 + 공통 CSS 파셜 (root_index / market_dashboard 가 include)
```

산출물 디렉토리:
```
data/output/
├── {ticker}/{YYYY-MM-DD}.html   종목별 일일 리포트
├── {ticker}/index.html          종목별 발행 목록
├── market/{YYYY-MM-DD}.html     ETP 인터랙티브 대시보드 (ETF/ETN/ELW 탭 + 정렬·필터·검색 + 인사이트 5, --market 빌드 시 날짜별 누적)
└── index.html                   루트 인덱스 (최신 시장 요약 + 인사이트 5 + 종목 목록 + 시장 대시보드 날짜 링크)
```

**모듈 의존성 규칙 (위반 금지)**:
- `analyzers/`는 `mcp_clients/`, `collectors/`, `fallbacks/`, `renderer/` 를 import하지 않는다 (순수 함수)
- `renderer/`는 `mcp_clients/`, `collectors/`, `fallbacks/` 를 import하지 않는다 (raw 데이터를 직접 만지지 않음)
- `validators/`는 어떤 src 모듈도 import하지 않는다 (파일 시스템·인자만 본다)
- `main.py`만이 위 모든 모듈을 조립한다

## 3. 환각 방지 메커니즘 (변경·삭제 금지)

### 3.1 메타 트리플 wrapping
모든 MCP/스크래핑 응답은 다음 형태로 감싼다:
```python
{
  "data": <원본>,
  "source": "korea-stock-mcp:get_stock_price",
  "tool_args": {"ticker": "329180", ...},
  "fetched_at": "<ISO 8601 UTC>"
}
```
이 dict 그대로 `data/raw/{date}/{name}.json`에 저장한다.

### 3.2 사후 숫자 대조
`render_html` 후 반드시 `verify_html_against_raw()`를 호출하고, 결과를 HTML 하단에 표시한다. 검증을 비활성화하지 마라.

### 3.3 LLM 코멘트 (Phase 2, 2026-05-09 도입)
- 어떤 Python 코드도 OpenAI, Anthropic, Google AI **SDK 를 자동 호출하지 않는다**. LLM 코멘트는 Claude Code 세션 (이 어시스턴트) 이 직접 작성한 후 `data/llm/{ticker}/{date}.json` 사이드카로 저장한다.
- main.py 빌드 시 `src/llm/inject.py` 가 사이드카를 읽어 슬롯에 inject 한다. 사이드카가 없으면 Phase 1 의 룰 기반 fallback 을 그대로 사용한다.
- 슬롯 내 **모든 numeric claim** 은 `<span data-cite="{file}:{json-path}:{value}">` 로 wrap 한다.
- `src/validators/citations.py` 가 모든 data-cite 를 raw 파일에서 검증. mismatch 비율 >5% 면 배지 fail.
- 정성적 표현 (예: "강세 추세 유지") 은 자유, 그러나 수치는 반드시 raw 출처 매칭.

### 3.4 출처 표기
HTML footer에 항상 다음을 표시:
- 데이터 소스 (DART, KRX, 사용된 MCP 서버명)
- `Generated YYYY-MM-DD HH:MM KST`
- "정보 제공 목적이며 투자 조언이 아님" 디스클레이머

## 4. 새 데이터 소스 추가 시 절차

1. **MCP가 있는지 먼저 확인.** `search_mcp_registry`로 검색.
2. MCP가 있으면 `src/mcp_clients/{소스명}.py` 생성, 모든 fetch 함수는 §3.1 메타 트리플 형식으로 반환
3. MCP가 없고 공식 API가 있으면 `src/collectors/{소스명}.py` 생성 (직접 HTTP 호출)
4. 공식 API도 없고 스크래핑이 필요하면 `src/scrapers/{소스명}.py` 생성, 단 robots.txt 확인 + User-Agent 명시 + 1초 이상 sleep
5. **새 소스 추가 시 README.md의 "데이터 소스" 표 갱신**

## 5. 코딩 컨벤션

### 5.1 Python
- Python 3.11+
- 모든 함수에 type hint
- 외부 호출(network, subprocess, file IO)은 async가 자연스러운 곳에서만 async, 그 외는 동기
- exception을 삼키지 말고 logging으로 남기고 재발생 또는 명시적 fallback
- `print` 금지, `logging` 사용
- 매직 넘버 금지 — `config.py`에 상수로 빼라

### 5.2 임포트 순서
```python
# 표준 라이브러리
import asyncio
from pathlib import Path

# 3rd party
import pandas as pd
from jinja2 import Environment

# 프로젝트 내부
from src.config import TARGET
from src.analyzers import price as price_analyzer
```

### 5.3 네이밍
- `fetch_*` — 외부에서 데이터 가져오는 함수 (mcp_clients, collectors)
- `parse_*` — 원본 응답 → 정규화된 dict/df
- `analyze_*` / `enrich_*` — 분석 함수
- `render_*` — HTML/차트 생성
- `verify_*` — 검증 함수

### 5.4 한글 처리
- 한국어 주석/문자열 OK, 모든 파일 UTF-8
- HTML lang="ko", 콤마는 천단위 구분자, 등락 색상은 한국 관습 (상승 빨강 #e85d4a, 하락 파랑 #3a7bd5)
- 날짜 표기: `YYYY-MM-DD` (KST 명시 필요 시 ` KST` suffix)

## 6. 디자인 시스템 (renderer/templates/dashboard.html.j2)

### 6.1 디자인 토큰 (변경 시 일관되게)
```css
--bg: #0f0f10
--surface: #16161a
--border: #26262b
--text: #e8e6e3
--muted: #7a7a82
--up: #e85d4a       /* 상승 (한국 관습) */
--down: #3a7bd5     /* 하락 */
--accent: #d4a574   /* warm gold */
--accent-soft: #9c8cb6  /* dusty mauve */
```

### 6.2 폰트
- Display: Fraunces (italic accent용, 헤더에만)
- Numerics: JetBrains Mono (가격, 시그널, 테이블 숫자)
- Body: Noto Sans KR (한글 본문)
- 신규 폰트 도입 금지 (사용자가 generic AI 미감을 싫어함)

### 6.3 차트
- Plotly CDN 사용 (현재 v2.35.2)
- `chart_builder._LAYOUT_BASE`에 정의된 다크 테마 일관 적용
- 새 차트는 반드시 `_to_div()` 거쳐 HTML div 문자열로 반환
- legend는 차트 위쪽 가로 배치, hover label 다크 테마

## 7. 자동화 운영

### 7.1 GitHub Actions cron — 사용 안 함
GitHub Actions cron 은 도입하지 않는다. pykrx 가 data.krx.co.kr 로그인을 한국 IP 에서만 안정적으로 처리하기 때문 (Actions 미국 IP 에서 차단 위험).

### 7.2 로컬 Windows 작업 스케줄러 + GitHub Pages (현재 운영)
사용자 호스트(Windows)에서 매시간 빌드 후 정적 HTML 만 GitHub Pages 로 push. `scripts/hourly.ps1` 가 다음을 책임진다:
- 평일 09–16시 KST 외 즉시 종료 (주말 / 장외시간)
- 한국 공휴일은 ``holidays`` 패키지로 스킵
- 종목별 빌드 → ``data/output/`` HTML 변경 시에만 commit/push (의미 없는 push 방지)

등록 명령 (관리자 PowerShell):
```
schtasks /create /sc HOURLY /tn "KRX_Reporter" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\pjt\reporter\scripts\hourly.ps1" /st 09:00 /f
```

레포 push 대상: `bizsinsightclub/stockreport` (공개) — `data/output/**/*.html` 만. raw / cache / `.env` 는 `.gitignore` 로 절대 push 안 됨.

### 7.3 secrets (로컬 `.env` 만, GitHub 에는 절대 push 금지)
- `DART_API_KEY`: opendart.fss.or.kr (공시·재무 XBRL · induty_code)
- `KRX_API_KEY`: openapi.krx.co.kr (선택, 미발급 시 pykrx 자동 fallback)
- `KRX_ID` / `KRX_PW`: data.krx.co.kr 로그인 (pykrx 1.2.x 인증)

`.env` 는 `.gitignore` 에 포함. 공개 레포에 절대 들어가지 않도록 매 commit 전 staged 목록 확인.

## 8. 의존성 관리

- `requirements.txt`만 사용 (Poetry/pdm 도입 금지 — 사용자 환경 단순화)
- 새 의존성 추가 시 그 이유를 PR/커밋 메시지에 명시
- 무거운 의존성(`tensorflow`, `tf`, `scikit-learn` 같은 50MB+) 금지 — Actions 빌드 시간 늘어남
- 가능한 한 stdlib과 pandas/numpy/plotly로 해결

## 9. Claude Code가 작업 시작 시 따라야 할 워크플로우

1. **HANDOFF.md를 먼저 읽는다** (특히 §5 "즉시 확인이 필요한 항목")
2. 사용자 요구를 듣고 §0 Top Rules와 충돌하지 않는지 확인
3. 영향받는 파일을 `view`로 모두 읽는다 — 추측으로 수정하지 않는다
4. 새 데이터 소스라면 §4 절차 따른다
5. 새 차트/UI라면 §6 디자인 토큰 재사용
6. 변경 후 `python test_render.py`로 더미 데이터 렌더 확인
7. 실 데이터 테스트는 `python -m src.main` (API 키 필요)
8. **§3 환각 방지 메커니즘이 영향받는 변경**은 사용자에게 확인 요청

## 10. 자주 묻는 질문 (FAQ for AI assistants)

**Q: LLM API를 추가해도 되나?**
A: Python 코드에서 OpenAI/Anthropic/Google SDK **자동 호출은 금지**. Phase 2 진입(2026-05-09)으로 LLM 코멘트는 도입됐지만, 호출 주체는 Claude Code 세션(이 어시스턴트) 자체이며 결과물을 `data/llm/{ticker}/{date}.json` 사이드카로 저장한다. main.py 가 그 사이드카를 읽어 슬롯에 inject. 새 SDK 의존성 추가 필요 없음. 모든 numeric claim 에 `<span data-cite>` 의무 — `validators/citations.py` 가 검증.

**Q: 차트 라이브러리를 Recharts/Chart.js로 바꿔도 되나?**
A: 안 된다. Python에서 서버사이드 렌더 후 정적 HTML에 embed하는 게 핵심 (Actions 환경에서 작동). Plotly는 그래서 선택됐다.

**Q: pykrx로 직접 가져오면 더 간단하지 않나?**
A: 임시 백업으로는 가능 (HANDOFF §5.2). 메인 경로는 MCP를 유지한다 — 사용자 학습 목적과 확장성 고려.

**Q: 검증기가 false positive를 너무 많이 잡는데?**
A: HANDOFF §5.3 참조. SVG/script 영역 제외 필터링이 다음 작업 우선순위.

**Q: requirements.txt를 pyproject.toml로 바꿔도 되나?**
A: 안 된다 (§8). 사용자 환경 단순화 우선.

**Q: 새 종목 분석을 추가하라는 요청이 왔다.**
A: 더 이상 `TARGET` 상수가 없다. CLI 인자(`python -m src.main <ticker>`)로 종목 코드를 전달하면 피어가 자동 선정된다. ticker별 디렉토리(`data/output/{ticker}/`)와 ticker_index/ root_index 가 자동 갱신된다.

**Q: Phase 2 는 무엇이 추가됐나?**
A: 슬래시 커맨드 (`.claude/commands/report-stock.md`), `src/llm/inject.py` (LLM 사이드카 → 슬롯 inject), `src/validators/citations.py` (claim-level citation 검증). §0.3 / §3.3 갱신 완료 (2026-05-09).

**Q: LLM 슬롯 작성은 어떻게 시작하나?**
A: 사용자가 `/report-stock <ticker>` 입력 → 슬래시 커맨드 본문 따라 (1) `python -m src.main <ticker>` 빌드 → (2) `data/raw/{date}/{ticker}_*.json` 읽고 numeric 인지 → (3) 슬롯 6개 작성 + citation 포함하여 `data/llm/{ticker}/{date}.json` 저장 → (4) `python -m src.main <ticker>` 재빌드 → (5) `validators/citations.py` 통과 확인.

## 11. 변경 시 함께 갱신해야 하는 문서

- 데이터 소스 추가/변경 → README.md, HANDOFF.md
- API 키 추가 → README.md, HANDOFF.md, .env.example, .github/workflows/daily.yml
- 새 모듈 추가 → CLAUDE.md §2 디렉토리 매핑
- 핵심 결정사항 변경 → HANDOFF.md §2 의사결정 표 + 사용자 confirm
- 디자인 토큰 변경 → CLAUDE.md §6, charts.py, dashboard.html.j2 동시
