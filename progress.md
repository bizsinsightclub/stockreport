# 진행 상황 — 2026-05-09 (3차 갱신)

> 다음 세션에 이 파일을 먼저 읽고 §1 "현재 상태" → §3 "다음 세션 우선순위" 순서로 보면 됩니다.

## 1. 현재 상태 (Phase 1 + Phase 2 + Phase 3 코어 완료)

### 완료 (이번 세션)
- §3.B 검증기 unmatched 0% (analyzer 파생값을 enriched.json 으로 raw_dir 에 저장)
- §3.C 수급 차트 외국인 강조 + 억원 단위 + 한글 표시명 정상화
- **§3.D Phase 2 — LLM 슬롯 + claim-level citation 검증 시스템**
  · `src/llm/inject.py`, `src/validators/citations.py`, `.claude/commands/report-stock.md`
  · `data/llm/{ticker}/{date}.json` 사이드카 → main.py 자동 inject
  · 슬롯 안 모든 numeric claim 에 `<span data-cite="file:path:value">` 의무
- LLM sidecar 디테일 보강 (매집/매도 시그널 포함, 두 종목 모두)
- **Phase 3 신규 기능 3 셋**:
  1. **재무 valuation 6 카드** (PER/PBR/EPS/BPS/ROE/부채비율) — pykrx + DART
  2. **애널리스트 TP 컨센서스** (네이버 m.stock.naver.com `/integration` API + `BaseTPProvider` adapter)
  3. **§1.6 거래활성도 / 수급 강도** — 회전율 카드 + 거래량 차트(60일 MA) + 외/기/개 비중 stacked
- pykrx `adjusted=True` 시 거래대금 누락 버그 → `adjusted=False` 로 변경

### 빌드 결과 (2026-05-08, 두 종목)

| 종목 | numbers | citations | 비고 |
|---|---|---|---|
| 329180 HD현대중공업 | 124/124 pass | 24/24 pass | TP 818,188원 / +24.34% upside / ROE 15.15% |
| 456160 지투지바이오 | 107/107 pass | 23/23 pass | TP 미커버 / 적자(PER N/A) / ROE -20.72% |

GitHub: `https://github.com/bizsinsightclub/stockreport` (latest commit `32600be`).
Pages: `https://bizsinsightclub.github.io/stockreport/`.

## 2. 환경 상태 (변경 없음)

- Python 3.11.9 / 의존성 12개 / `.env` 4 키 (KRX_API_KEY, DART_API_KEY, KRX_ID, KRX_PW)
- Git origin: `bizsinsightclub/stockreport` (공개)
- 자동화: `scripts/hourly.ps1` (평일 09–16시 KST + 한국 공휴일 스킵, schtasks 등록은 사용자 수동)

## 3. 다음 세션 우선순위 (사용자 신규 요청, 2026-05-09 후반)

### A. TP 컨센서스 추세성·시간성 보강 (보류 중 — 데이터 탐색 단계)

**현재 한계** (사용자 지적):
- 네이버 `/integration` 의 `consensusInfo` 가 단일 평균 + createDate 만 반환
- 어느 분석가가 언제 발표했는지 timeline 불명
- 오래된 발표가 섞일수록 평균의 신뢰도 하락

**요구사항**:
1. **지난 1년 데이터 범위** 한정
2. **분석가별 발표 history** (같은 사람의 TP 변경 추이 = 상향/하향 흐름 가시화)
3. **발표일별 timeline** (날짜 순서 + 해당 시점 종가 비교 가능)
4. UI: 단일 카드가 아니라 산점도/타임라인 차트 — "최근 6M 분석가 TP scatter + 평균선" 형태

**탐색해야 할 데이터 소스**:
- 네이버 모바일: `m.stock.naver.com/domestic/stock/{ticker}/research` 페이지의 JS 안에 더 자세한 endpoint 있을 가능성. `/api/research-report/?itemCode=...` 또는 `/api/stock/{ticker}/research/all` 같은 형식. **사용자가 `WebFetch` 도구 호출을 한 번 거부하여 탐색 미완** — 다음 세션 시작 시 사용자 동의 받고 재시도.
- 한경 컨센서스 (`consensus.hankyung.com`) — 분석가/증권사별 보고서 list 풍부
- 네이버 데스크탑 `coinfo.naver?code=...&target=consensus` 페이지 스크래핑

**구현 방향**:
- `src/scrapers/tp_history.py` 신규 — 분석가별 history list 반환
- `BaseTPProvider` 인터페이스 확장 (`fetch_history(ticker) -> list[dict]`)
- `src/renderer/charts.py` 신규 차트: TP scatter timeline (X=날짜, Y=목표가, color=분석가/증권사)
- 6개월~1년 데이터만 필터, 1년 초과 발표는 graphical 풍자 표시 또는 제외
- LLM 슬롯에 분석가 평균 변화 추세 인용 가능 (예: "최근 6M 평균 TP 상향 +X% / 분석가 N명 커버")

### B. 메인 화면 (root index) 시장 전반 추세 — ETF·ELW·ETN 일별 매매정보

**현재 root index** (`data/output/index.html`): 분석된 종목 리스트만 표시. 시장 전반 컨텍스트 없음.

**사용자 요청**: 종목 선택 전 메인 화면에서 다음 추세 확인 가능해야:
- ETF 일별 매매정보
- ELW 일별 매매정보
- ETN 일별 매매정보

**컬럼**: 기관·기준일자·종목명·시가(현재가)·종가·거래량·상장좌수·시가총액

**의도**: "기관들이나 기준일자" — 즉 어느 기관(자산운용사) 의 어느 ETF/ETN 이 어떻게 거래되는지 한눈에 보고 시장 흐름 인사이트.

**데이터 소스 후보**:
- KRX OpenAPI: `etf/etf_bydd_trd`, `etf/elw_bydd_trd`, `etf/etn_bydd_trd` 엔드포인트 (현재 401 — **사용자가 KRX 포털에서 해당 API 추가 신청해야** unblock)
- pykrx: `get_etf_ticker_list`, `get_etf_ohlcv_by_date`, `get_etn_ticker_list`, `get_etf_ticker_name` 등 — KRX_ID/KRX_PW 인증 통과 상태에서 작동
- 네이버 finance ETF 섹션 (보조)

**UI 구조 (제안)**:
- root index 페이지 상단: 시장 요약 카드 (KOSPI/KOSDAQ 종합 + USD/KRW)
- 그 아래 3 탭 또는 3 섹션: ETF / ELW / ETN
- 각 섹션: 거래대금/거래량 상위 N개 표 (기관 운용사·종목·시가·종가·거래량·상장좌수·시가총액)
- 디자인: 현재 dashboard 토큰 그대로 (`COLOR_BG`/`COLOR_SURFACE`/`COLOR_ACCENT` 등)

**구현 방향**:
- `src/collectors/krx_etf.py` 또는 `src/fallbacks/pykrx_etf.py` 신규 — 일별 ETF/ELW/ETN 거래 데이터 수집 (메타 트리플)
- `src/analyzers/market_overview.py` 신규 — 거래 상위 N 추출 + 운용사 그룹 (ETF 운용사 매핑)
- `src/renderer/templates/root_index.html.j2` 갱신 — 시장 요약 + 3 섹션 추가
- `src/main.py` 또는 신규 `src/market_overview_main.py` — 시장 전체 빌드 진입점 (종목 빌드와 별도)
- `scripts/hourly.ps1` 에 시장 빌드 추가 (또는 `scripts/market_hourly.ps1` 분리)

**원칙 보존**:
- 모든 외부 데이터는 메타 트리플 wrap (CLAUDE.md §3.1)
- raw 는 `data/raw/{date}/_market_etf.json` 등으로 저장
- numbers / citations 검증기 적용 (LLM 슬롯 도입 시)

### C. 인사이트 코멘트 디테일 (사용자 명시)

> "이런 정보들을 통해 인사이트를 얻을 수 있는 내용으로 디테일하고 알기쉽게 작성되어야 해"

ETF/ELW/ETN 표 위에 LLM 슬롯 추가 — 시장 자금 흐름 한 줄 평. 예:
- "최근 5거래일 ETF 거래대금 상위는 KODEX 200·TIGER 미국나스닥... 자금 미국주식 ETF 로 이동 추세"
- "ELW 거래량 급증 종목은 코스피200 콜형... 단기 변동성 베팅 수요 확대"

이런 코멘트는 Claude Code 세션이 ETF/ELW/ETN raw 보고 작성 + citation 의무 (Phase 2 메커니즘 그대로).

신규 슬래시 커맨드 후보: `.claude/commands/market-overview.md` — root index LLM 코멘트 작성용.

## 4. 사용자가 직접 할 것 (변경 없음)

1. **schtasks 등록** (관리자 PowerShell):
   ```
   schtasks /create /sc HOURLY /tn "KRX_Reporter" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\pjt\reporter\scripts\hourly.ps1" /st 09:00 /f
   ```
2. **GitHub Pages 활성화** — 이미 작동 중 (`https://bizsinsightclub.github.io/stockreport/` 200 OK 확인됨)
3. ⚠ **KRX_PW 변경** — 평문 채팅 노출
4. (B 작업 위해) **KRX OpenAPI 포털에서 ETF/ELW/ETN 일별 매매 API 추가 신청** — 401 unblock 시 더 정확한 데이터 사용 가능. pykrx fallback 만으로도 작동 가능

## 5. 빠른 재개 명령어

```powershell
# (1) 환경 확인
py -3.11 --version
Get-Content C:\pjt\reporter\.env | Select-String "KRX_ID|DART|KRX_API"

# (2) 두 종목 빌드
Set-Location C:\pjt\reporter
py -3.11 -m src.main 329180 --date 2026-05-08
py -3.11 -m src.main 456160 --date 2026-05-08

# (3) 검증 결과
Get-Content C:\pjt\reporter\data\output\329180\2026-05-08.validation.json -Raw
Get-Content C:\pjt\reporter\data\output\329180\2026-05-08.citations.json -Raw

# (4) Pages 확인
Start-Process "https://bizsinsightclub.github.io/stockreport/data/output/329180/2026-05-08.html"

# (5) LLM sidecar 갱신 (slash command 데모)
# 채팅에서: /report-stock 329180  (이 세션이 raw 읽고 6 슬롯 작성 + citation)
```

## 6. 이번 세션 commits 요약

| Commit | 내용 |
|---|---|
| `2af0bd8` | validator unmatched 0% (enriched.json 추가) |
| `e79bc43` | 수급 차트 외국인 강조 + 억원 단위 |
| `65776ec` | Phase 2 LLM 슬롯 + citation 시스템 |
| `2e0faf6` | .gitignore — .claude/commands negation |
| `fbdee19` | LLM 슬롯 디테일 보강 (매집/매도 시그널) |
| `7602636` | Phase 3-1 valuation 6 카드 |
| `f27f606` | Phase 3-2 TP 컨센서스 + adapter |
| `32600be` | Phase 3-3 §1.6 거래활성도 + adjusted=False fix |

## 7. 알려진 미해결 / 메모

- **KRX OpenAPI 401**: 키 자체는 유효. ETF/ELW/ETN 등 추가 API 는 portal 신청 필요. 자동 피어 매칭은 DART induty 우회로 해결됨
- **TP 컨센서스 시간성**: 위 §3.A 본격 작업 필요 (단일 평균 → history scatter)
- **Root index 시장 전반**: 위 §3.B 본격 작업 필요 (ETF/ELW/ETN)
- **`KRX_PW` 평문 노출**: §4.3 처리 필요
- **자동 빌드 noise commits**: hourly.ps1 이 매시간 push하면 LLM sidecar 가 같은 날짜 동안 안 변해도 generated_at 이 매시간 바뀌어 noise. 차후 generated_at 을 일자 단위로 truncate 하거나 git diff 가 generated_at 단독 변경이면 commit 스킵 로직 필요
- **섹션 번호 일관성**: §1.6 추가 후 02/SEVEN, 03/SEVEN 추가했으나 다른 섹션은 03/FIVE 등 그대로. 일관성 정리 가능
- **자동 빌드 새 코드 호환**: §1.6 회전율 등 새 데이터는 `adjusted=False` 빌드에서만 작동. 기존 빌드 결과(자동화)도 자동으로 반영됨

## 8. plan 파일 위치

`C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md` — Phase 1 plan. Phase 2/3 spec 은 본 progress.md 와 commit history 가 source of truth.
