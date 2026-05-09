# 진행 상황 — 2026-05-09 (4차 갱신, 종료 시점)

> 다음 세션에 이 파일을 먼저 읽고 §1 "현재 상태" → §3 "다음 세션 우선순위" 순서로 보면 됩니다.

## 1. 현재 상태 — Phase 1 / 2 / 3 / 4 모두 완료, lens 시스템 본격 활용 진입

### Phase 마일스톤 (이번 세션 누적)
- **Phase 1**: 결정론 코어 (시세·수급·공시·재무·피어·거시 7섹션) ✅
- **Phase 2**: LLM 슬롯 + claim-level citation 검증 (`src/llm/inject.py`, `src/validators/citations.py`, `.claude/commands/report-stock.md`) ✅
- **Phase 3**: 재무 valuation 6 카드 + (보류) TP 컨센서스 + §1.6 거래활성도 ✅
- **Phase 4**: ETF/ETN/ELW 시장 root index (KRX OpenAPI + pykrx fallback) ✅
- **Phase 5 — lens 시스템**: 8 섹션 × 9 코멘트 (3 관점 × 3 기간) 토글 UI + sidecar 스키마 ✅

### 종목별 LLM sidecar 완성도

| 종목 | 5 슬롯 | 공시 14 슬롯 | lens 8 섹션 × 9 = 72 코멘트 | numbers | cites |
|---|---|---|---|---|---|
| 329180 HD현대중공업 | ✅ 디테일 | ✅ 14건 | ✅ **전 섹션 완성** | 385/385 pass | 216/216 pass |
| 290650 엘앤씨바이오 | ✅ 디테일 | (LLM lens) | ⚠ s2_tech 만 (9/72) | 152/152 pass | 52/52 pass |
| 456160 지투지바이오 | ✅ 디테일 | — | ⚠ 미작성 (0/72) | 107/107 pass | 23/23 pass |

GitHub: `https://github.com/bizsinsightclub/scakreport` 의 마지막 커밋
Pages: `https://bizsinsightclub.github.io/stockreport/`

### 페이지 구조 (현재 작동)
- **루트** (`data/output/index.html`): 시장 요약 (ETF 1099 / ETN·ELW 401 placeholder) + 운용사별 거래대금 + 분석 종목 monogram 리스트
- **종목 페이지** (`data/output/{ticker}/{date}.html`):
  - 헤더 + TP 카드 (placeholder, 유료 API 키 준비 중)
  - 시세·기술·수급·공시·재무·피어·거시 7섹션
  - **각 섹션 끝에 lens 토글 panel** (관점 × 기간 9 코멘트, fallback 시 placeholder)
  - 두 검증 배지 (numbers + citations)

## 2. 환경 상태 (변경 없음)

- Python 3.11.9 / 의존성 12개 (`requirements.txt`) / `.env` 4 키
- Git origin: `bizsinsightclub/stockreport`
- 자동화: `scripts/hourly.ps1` (평일 09–16시 KST + 한국 공휴일 스킵, schtasks 등록은 사용자 수동)

## 3. 다음 세션 우선순위 (남은 미작성)

### A. 290650 엘앤씨바이오 lens 확장 (가장 큰 작업)
- 현재 s2_tech 9 코멘트만 작성됨
- 미작성 7 섹션 × 9 = **63 코멘트** 필요
  - s1_price, s15_flow, s16_volume, s3_disc, s4_fin, s5_peer, s6_macro
- 작성 가이드: `.claude/commands/report-stock.md` 본문 참고
- 한 가지 주의: 290650 은 PER/EPS = null (적자) — int/exp 슬롯에서 PBR 7.59, ROE -66.29%, 부채비율 118.98% 위주 인용

### B. 456160 지투지바이오 sidecar lens 추가
- 현재 5 기본 슬롯만 작성됨
- 미작성 8 섹션 × 9 = **72 코멘트** 필요
- 데이터 특이점: PER N/A (적자), week52_pos 25.5% (저점권), MA 골든 + MACD 상승 (전환 시그널), 외국인 -77.5억 vs 기관 +231.8억 (기관 매수 dominant — 329180 와 정반대 패턴)

### C. TP 컨센서스 도입 재개 (유료 API 키 받은 후)
- `BaseTPProvider` 추상화는 완성. 신규 클래스 (e.g. `FnGuideTPProvider`) 구현 + main.py 활성화 라인 한 줄로 가능
- progress.md §3.A 의 1년 history + 분석가별 추세 요건은 그 시점에 재설계

### D. ETN/ELW 시장 데이터 unblock
- KRX OpenAPI ETP 3개 API (`etp/etf_bydd_trd`, `etp/etn_bydd_trd`, `etp/elw_bydd_trd`) 모두 401
- 사용자가 `https://openapi.krx.co.kr` → My Page → 신청 추가 후 승인 받으면 코드 변경 없이 자동 활성화 (ETF는 pykrx 사용 중이지만 KRX API 일관성 권장)

### E. 시장 root index LLM 인사이트 코멘트 (사용자 의도)
- 사용자 명시: "이런 정보들을 통해 인사이트를 얻을 수 있는 내용으로 디테일하고 알기쉽게"
- 신규 슬래시 커맨드 후보: `.claude/commands/market-overview.md`
- 작성 슬롯: ETF 운용사별 자금 흐름 / ETN/ELW 트렌드 한 줄 평
- root_index.html.j2 에 LLM 슬롯 + citation 메커니즘 추가 필요

## 4. 사용자가 직접 할 것 (변경 없음)

1. **schtasks 등록** (관리자 PowerShell):
   ```
   schtasks /create /sc HOURLY /tn "KRX_Reporter" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\pjt\reporter\scripts\hourly.ps1" /st 09:00 /f
   ```
2. **GitHub Pages 활성화** — 이미 작동 중
3. ⚠ **`KRX_PW` 변경** — 평문 채팅 노출
4. **KRX OpenAPI ETP 3개 API 추가 신청** — ETN/ELW unblock + ETF 일관성

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

## 6. 이번 세션 commits 요약 (전체)

| Commit | 내용 |
|---|---|
| `2af0bd8` | validator unmatched 0% (enriched.json) |
| `e79bc43` | 수급 차트 외국인 강조 + 억원 단위 |
| `65776ec` | Phase 2 LLM 슬롯 + citation 시스템 |
| `2e0faf6` | .gitignore — .claude/commands negation |
| `fbdee19` | LLM 슬롯 디테일 보강 (매집/매도) |
| `7602636` | Phase 3-1 valuation 6 카드 |
| `f27f606` | Phase 3-2 TP 컨센서스 + adapter |
| `32600be` | Phase 3-3 §1.6 거래활성도 |
| `c5992d7` | progress.md 갱신 (TP/시장 신규 요청) |
| `d29593f` | Phase 4 ETF/ETN/ELW root index |
| `da1adce` | 종목명 monogram + 290650 추가 |
| `ab6ed35` | Phase 5 lens 시스템 인프라 (8 섹션 토글) |
| `a8cdc6b` | demo: 329180 §2 lens 9 코멘트 |
| `bf49e0c` | demo: 329180 5 섹션 lens 45 + 14 공시 |
| (latest) | 329180 lens 전 섹션 (216/216) + 290650 sidecar 신규 |

## 7. 알려진 미해결 / 메모

- **TP 컨센서스 보류**: 무료 한국 금융 사이트 모두 robots.txt Disallow:/ 정책. NaverTPProvider 비활성. 유료 API (FnGuide / Refinitiv / Quantiwise) 키 준비 후 재개. CLAUDE.md §4 준수.
- **KRX OpenAPI 401**: ETF/ETN/ELW etp/* 3개 + stk_bydd_trd 등 모두 portal 신청 필요 (자동 피어는 DART induty 우회로 해결됨).
- **`KRX_PW` 평문 노출**: 채팅 기록 — 데이터 보호 위해 사용자 비밀번호 변경 권장.
- **자동 빌드 noise commits**: hourly.ps1 매시간 push 시 `generated_at` 만 변경되어도 commit 발생. 추후 generated_at 일자 단위 truncate 또는 git diff filter 필요.
- **섹션 번호 일관성**: §1.5/§1.6 추가 후 02/SEVEN, 03/SEVEN 추가했으나 다른 섹션은 03/FIVE 등 그대로 — UI 일관성 작업 가능.
- **공시 슬롯 (s3_disc_n)**: 329180 14건만 작성. 다른 종목은 fallback 텍스트 (정규식 추출).

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
