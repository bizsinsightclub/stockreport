# 진행 상황 — 2026-05-12 (5차 갱신, 종료 시점)

> 다음 세션에 이 파일을 먼저 읽고 §1 "현재 상태" → §3 "다음 세션 우선순위" 순서로 보면 됩니다.
> 이번 세션 회고는 `lesson_learned.md` 도 함께 보세요.

## 1. 현재 상태 — Phase 1~6 완료, KRX 키 전부 작동, ETP 인터랙티브 대시보드 도입

### Phase 마일스톤 (누적)
- **Phase 1**: 결정론 코어 (시세·수급·공시·재무·피어·거시 7섹션) ✅
- **Phase 2**: LLM 슬롯 + claim-level citation 검증 (`src/llm/inject.py`, `src/validators/citations.py`, `.claude/commands/report-stock.md`) ✅
- **Phase 3**: 재무 valuation 6 카드 + (보류) TP 컨센서스 + §1.6 거래활성도 ✅
- **Phase 4**: ETF/ETN/ELW 시장 root index (KRX OpenAPI + pykrx fallback) ✅
- **Phase 5 — lens 시스템**: 8 섹션 × 9 코멘트 (3 관점 × 3 기간) 토글 UI + sidecar 스키마 ✅
- **Phase 6 — 시장 페이지 강화** (2026-05-11/12 세션) ✅:
  - 메인 페이지 날짜별 아카이브 `data/output/market/{date}.html` (`render_market_archive`, `--market` 빌드마다 누적)
  - KRX OpenAPI ETP 게시 지연(T+1) 대응 — `_resolve_etp_date()` 가 실매매 데이터 있는 최근 영업일로 walk-back (`holidays` 패키지로 주말·공휴일 스킵, skeleton 행 필터)
  - **ETP 인터랙티브 대시보드** (`market_dashboard.html.j2`): ETF/ETN/ELW 탭 + 컬럼 정렬 + 운용사·기초자산 필터 + 검색, 데이터는 `<script type="application/json">` 임베드, 정렬/필터는 클라이언트 vanilla JS (새 의존성 0)
  - **시장 인사이트 5개** (`market_overview.compose_insights`, 룰 기반 결정론): 거래대금 1위 ETF+점유율 / 운용사 1위+점유율 / 상승·하락 비율 / 최대 상승 ETF / ETP 시장 규모
  - `root_index.html.j2` 슬림화 — 요약 카드 3 + 인사이트 5 + "시장 대시보드 →" 링크. 장황한 운용사 grid·top30·ETN·ELW 테이블은 대시보드로 이전. `_etp_styles.html.j2` 파셜로 디자인 토큰 공유.
  - README 전면 개편(쉬운 언어 + 스크린샷 5장, `docs/screenshots/`) + `docs/ai-literacy.md` (강의 보조자료 14k자) + `docs/superpowers/specs/2026-05-12-etp-market-dashboard-design.md`

### KRX / DART 키 상태 — **전부 작동 확인** (2026-05-11 세션)
- `KRX_API_KEY` (KRX OpenAPI): ETP `etp/{etf,etn,elw}_bydd_trd` 모두 status 200 + 데이터 정상 (5/8 기준 ETF 1099 / ETN 393 / ELW 2752). ⚠ 단 **당일분은 T+1 게시** — 빌드 시점엔 보통 직전 영업일이 최신 (walk-back 자동 처리). stk/ksq `bydd_trd` 도 200.
- `KRX_ID` / `KRX_PW` (pykrx data.krx.co.kr 로그인): 정상 (`craigkim112`). 시세·수급·시총·fundamental 수집.
- `DART_API_KEY`: 정상. corp_code 매핑·공시·재무 XBRL. (단 당해년도 분기 보고서는 공시 시점 전이라 status 013 "데이터 없음" — 정상)

### 종목별 LLM sidecar 완성도

| 종목 | 5 슬롯 | 공시 슬롯 | lens 8 섹션 × 9 = 72 | numbers | cites |
|---|---|---|---|---|---|
| 329180 HD현대중공업 — **2026-05-08** | ✅ 디테일 | ✅ 14건 | ✅ **전 섹션 완성** | 385/385 pass | 216/216 pass |
| 329180 HD현대중공업 — **2026-05-11** (신규) | ✅ 디테일 | ✅ 12건 | ⚠ 미작성 (0/72) | 133/133 pass | 24/24 pass |
| 290650 엘앤씨바이오 — 2026-05-08 | ✅ 디테일 | (LLM lens) | ⚠ s2_tech 만 (9/72) | 152/152 pass | 52/52 pass |
| 456160 지투지바이오 — 2026-05-08 | ✅ 디테일 | — | ⚠ 미작성 (0/72) | 107/107 pass | 23/23 pass |

GitHub: `https://github.com/bizsinsightclub/stockreport` (HEAD `49fae26`)
Pages: `https://bizsinsightclub.github.io/stockreport/` (push 후 1~5분 배포 지연 — raw.githubusercontent.com 은 즉시 갱신)

### 페이지 구조 (현재 작동)
- **루트** (`data/output/index.html`): 시장 요약 카드 3 + 인사이트 5 + "시장 대시보드 (날짜) →" 링크 + 분석 종목 monogram 리스트 + "지난 시장 리포트" 아카이브 목록
- **시장 대시보드** (`data/output/market/{date}.html`): 요약 카드 3 + 인사이트 5 + 운용사별 거래대금 grid + ETF/ETN/ELW 탭 인터랙티브 테이블 (정렬·필터·검색) + "← 메인으로"
- **종목 페이지** (`data/output/{ticker}/{date}.html`):
  - 헤더 + TP 카드 (placeholder, 유료 API 키 준비 중)
  - 시세·기술·수급·공시·재무·피어·거시 7섹션, 각 섹션 끝에 lens 토글 panel (관점 × 기간 9 코멘트, fallback 시 placeholder)
  - 두 검증 배지 (numbers + citations)

## 2. 환경 상태

- Python 3.11.9 / 의존성 12개 (`requirements.txt` — 새 의존성 추가 없음) / `.env` 4 키 전부 작동
- Git origin: `bizsinsightclub/stockreport` (HEAD `49fae26`)
- 자동화: `scripts/hourly.ps1` (평일 09–16시 KST + 한국 공휴일 스킵, schtasks 등록은 사용자 수동). ⚠ LLM 코멘트(`/report-stock`)는 아직 자동화 안 됨 — §3.A 참고.
- ⚠ `pytest` 미설치 — `tests/` 디렉토리 스위트 로컬 실행 불가. `test_render.py` 스모크는 돌지만 **선행 실패 상태** (lens 커밋이 dashboard 템플릿에 `llm_slot_keys` 게이트 추가했는데 test_render.py ctx 가 안 넘김). 또한 `test_render.py` 는 `TICKER=329180` 더미 데이터로 빌드 → **실제 329180 리포트를 덮어씀**. 함부로 돌리지 말 것.

## 3. 다음 세션 우선순위

### A. ⭐ LLM 코멘트 일일 자동화 — **사용자가 다음 세션에 결정 후 세팅 요청함**
- 사용자 의도: "보고서 만들라는 것을 매일 같은 시간에 주기적으로 Claude 에게 시키기"
- 결론(세션에서 정리): 결정론 빌드는 이미 `hourly.ps1` 로 자동화돼 있음. **LLM 코멘트(`/report-stock`)만 Claude 세션 필요** → `/schedule`(원격 routine)은 한국 IP·로컬 `.env`·로컬 `data/raw/` 접근 불가라 부적합. **Windows 작업 스케줄러 + `claude` 헤드리스(`claude -p "/report-stock <ticker>" --dangerously-skip-permissions`)** 가 정답.
- 세팅에 필요한 것 (사용자 답 대기 중 — 다음 세션 첫 질문):
  1. 대상 종목 (329180·290650·456160? 다른 리스트?)
  2. 실행 시각 (장 마감 후 18시? 아니면 ETP T+1 게시 고려 다음날 09시?)
  3. lens(8섹션×9) 까지 매일? 6 메인 슬롯만?
  4. 헤드리스 인증 — API 키 vs `--dangerously-skip-permissions`
- 답 받으면 만들 것: `scripts/report-llm-daily.ps1` 래퍼 + `.claude/settings.json` 권한 allowlist(`/update-config`) + `schtasks /create /sc DAILY /tn "KRX_Reporter_LLM" ...` 명령

### B. 329180 2026-05-11 lens 추가 (선택)
- 5/11 리포트는 6 메인 슬롯 + 12 공시 슬롯만 작성됨 (배지 둘 다 pass). lens 8 섹션 × 9 = 72 코멘트 미작성.
- 5/8 리포트는 lens 전 섹션 완성돼 있으니, 5/11 도 동일 수준 원하면 추가.

### C. 290650 엘앤씨바이오 lens 확장
- 현재 s2_tech 9 코멘트만. 미작성 7 섹션 × 9 = 63 코멘트.
- 주의: 290650 은 PER/EPS = null (적자) — int/exp 슬롯에서 PBR 7.59, ROE -66.29%, 부채비율 118.98% 위주 인용

### D. 456160 지투지바이오 sidecar lens 추가
- 현재 5 기본 슬롯만. 미작성 8 섹션 × 9 = 72 코멘트.
- 데이터 특이점: PER N/A (적자), week52_pos 25.5% (저점권), MA 골든 + MACD 상승 (전환 시그널), 외국인 -77.5억 vs 기관 +231.8억 (기관 매수 dominant — 329180 와 정반대)

### E. ELW 요약 카드 "상승/하락 0/0" polish (소)
- KRX OpenAPI elw_bydd_trd 응답에 `FLUC_RT` 가 비어서 gainers/losers=0/0. ELW 카드에서 상승/하락 줄 숨기거나, ELW 등락률 컬럼 자체를 빼는 게 깔끔.

### F. TP 컨센서스 도입 재개 (유료 API 키 받은 후)
- `BaseTPProvider` 추상화는 완성. 신규 클래스 (e.g. `FnGuideTPProvider`) 구현 + main.py 활성화 라인 한 줄.

### G. 시장 root index / 대시보드 LLM 인사이트 (선택, 사용자 과거 의도)
- 현재 인사이트 5개는 룰 기반. 더 디테일한 LLM 코멘트를 원하면 `.claude/commands/market-overview.md` 신규 + citation 메커니즘 추가. (다만 룰 기반으로도 충분하다는 판단이 이번 세션 설계 — 사용자 추가 요청 시에만)

## 4. 사용자가 직접 할 것

1. **schtasks 등록** (관리자 PowerShell) — 결정론 빌드:
   ```
   schtasks /create /sc HOURLY /tn "KRX_Reporter" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\pjt\reporter\scripts\hourly.ps1" /st 09:00 /f
   ```
2. **LLM 자동화 결정** — §3.A 의 4가지 질문에 답 → Claude 가 세팅
3. **GitHub Pages 활성화** — 이미 작동 중 (push 후 1~5분 배포 지연 정상)
4. ⚠ **`KRX_PW` 변경** — 과거 채팅에 평문 노출됨

## 5. 빠른 재개 명령어

```powershell
# (1) 환경 확인
py -3.11 --version
Get-Content C:\pjt\reporter\.env | Select-String "KRX_ID|DART|KRX_API"

# (2) 세 종목 + 시장 빌드
Set-Location C:\pjt\reporter
py -3.11 -m src.main 329180 --date 2026-05-08
py -3.11 -m src.main 456160 --date 2026-05-08
py -3.11 -m src.main 290650 --date 2026-05-08
py -3.11 -m src.main --market --date 2026-05-08

# (3) 검증 결과 빠른 확인
foreach ($tk in '329180','456160','290650') {
  Get-Content "C:\pjt\reporter\data\output\$tk\2026-05-08.citations.json" -Raw
}

# (4) Pages 확인 (1-2분 후 갱신)
Start-Process "https://bizsinsightclub.github.io/stockreport/"

# (5) LLM sidecar 갱신 (slash command)
# 채팅: /report-stock 290650
# (또는 직접 data/llm/{ticker}/{date}.json 편집 후 재빌드)
```

## 6. commits 요약

### ~2026-05-09 (4차까지)
| Commit | 내용 |
|---|---|
| `65776ec` | Phase 2 LLM 슬롯 + citation 시스템 |
| `7602636` `f27f606` `32600be` | Phase 3 valuation / TP adapter / §1.6 거래활성도 |
| `d29593f` | Phase 4 ETF/ETN/ELW root index |
| `da1adce` | 종목명 monogram + 290650 추가 |
| `ab6ed35` | Phase 5 lens 시스템 인프라 (8 섹션 토글) |
| `a8cdc6b` `bf49e0c` `f4477a0` | demo: 329180 lens 전 섹션 (216/216) + 290650 sidecar |

### 2026-05-11 / 12 (5차 — 이번 세션)
| Commit | 내용 |
|---|---|
| `28de485` | docs: README 전면 개편 (쉬운 언어 + 스크린샷 5장) + `docs/ai-literacy.md` 강의 보조자료 |
| `e5e6b9f` | report(329180): 2026-05-11 실데이터 리포트 (6 슬롯, citation, 배지 둘 다 pass) + 메인 페이지 갱신 |
| `6ccdca6` | feat(market): 메인 페이지 날짜별 아카이브 `data/output/market/{date}.html` |
| `921330a` | fix(market): KRX OpenAPI ETP 게시 지연 → 최근 실매매 영업일 walk-back (`_resolve_etp_date`, `holidays`) |
| `aa507fd` | docs(spec): ETP 인터랙티브 대시보드 + 인사이트 5개 설계 |
| `49fae26` | feat(market): ETP 인터랙티브 대시보드 (탭+정렬+필터+검색, vanilla JS) + 시장 인사이트 5개 (룰 기반) + root_index 슬림화 + `_etp_styles.html.j2` 파셜 |

## 7. 알려진 미해결 / 메모

- **KRX OpenAPI ETP T+1 게시 지연**: `etp/{etf,etn,elw}_bydd_trd?basDd=오늘` → `OutBlock_1: []`. 비영업일(일요일 등) 조회 시 종목 행은 오지만 `TDD_CLSPRC`·`ACC_TRDVAL` 등 매매 필드가 빈 문자열(skeleton). `_resolve_etp_date()` 가 실매매 데이터 있는 최근 영업일로 walk-back. → 그래서 시장 페이지의 "시장 기준일" 이 빌드일보다 며칠 전일 수 있음 (정상).
- **GitHub Pages 배포 지연**: push 후 1~5분 (가끔 더). `raw.githubusercontent.com/.../main/...` 은 즉시 갱신되므로 그걸로 레포 반영 여부 확인. 로컬 파일은 즉시 정상.
- **`pytest` 미설치 + test_render.py 위험**: `tests/` 스위트 로컬 실행 불가. `test_render.py` 는 (1) lens 커밋 이후 `data-llm-slot="brief"` assertion 선행 실패 (ctx 에 `llm_slot_keys`/`slots` 안 넘김), (2) `TICKER=329180` 더미로 빌드 → 실제 329180 리포트 덮어씀 + `update_root_index()` 로 index.html 도 덮어씀. 함부로 돌리면 `git checkout HEAD -- data/output/` 로 복구해야 함.
- **`git stash -u` + 워킹트리 변경 작업 + 조용한 `git stash pop` 실패 = 편집 유실**: 이번 세션에서 발생. `git stash -u` 후 test_render.py 가 `data/output/` 에 쓰니까 pop 시 충돌 → `>/dev/null 2>&1` 가 실패를 숨김 → src 편집이 stash 에 갇힘. 교훈: stash 후 워킹트리 건드리는 명령 돌리지 말 것, pop 출력 절대 숨기지 말 것. (`lesson_learned.md` 참고)
- **TP 컨센서스 보류**: 무료 한국 금융 사이트 모두 robots.txt Disallow:/. NaverTPProvider 비활성. 유료 API 키 준비 후 재개. CLAUDE.md §4 준수.
- **`KRX_PW` 평문 노출**: 과거 채팅 기록 — 사용자 비밀번호 변경 권장.
- **자동 빌드 noise commits**: hourly.ps1 매시간 push 시 `generated_at` 만 변경되어도 commit 발생. 추후 truncate 또는 diff filter 필요.
- **ELW 등락률 부재**: KRX OpenAPI elw_bydd_trd 에 `FLUC_RT` 없음 → ELW 카드 상승/하락 0/0. §3.E polish 대상.
- **공시 슬롯 (s3_disc_n)**: 329180 (5/8 14건, 5/11 12건) 만 작성. 다른 종목은 fallback 텍스트 (정규식 추출).

## 8. 데이터 구조 reference (lens 작성 시 자주 쓰는 path)

```
{ticker}_enriched.json:
  data.header.{price_now, change_pct, as_of, direction}
  data.signals.{rsi, week52_pos, trend_ma, macd_dir, bollinger}
  data.flow_summary.{foreign|institution|individual}_{net_5d|net_last_day}_{krw|oku}
  data.volume_metrics.{today_traded_oku, avg60_traded_oku, ratio_pct,
                       turnover_pct, today_volume, avg60_volume}
  data.valuation.{per, pbr, eps, bps, roe, debt_ratio, as_of_period}
  data.peer_rows[i].{name, ticker, close, change_pct, volume}
  data.macro_cards[0].{name, value, delta, direction}
```

trivial 처리 token (citation 면제): 0~31 정수, 1900~2100 (연도), 50/52/60/70/80/90/100/120/200/252.

## 9. plan 파일 위치

`C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md` — Phase 1 plan. Phase 2-5 spec 은 본 progress.md + commit history + `.claude/commands/report-stock.md` 가 source of truth.
