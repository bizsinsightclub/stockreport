# 진행 상황 — 2026-05-09

> 다음 세션에 이 파일을 먼저 읽고 §1 "현재 상태"와 §3 "다음 세션 우선순위"부터 보면 됩니다.

## 1. 현재 상태 (Phase 1 ✅ 완료, 자동화 + 자동 피어 매칭 ✅ 완료)

`C:\pjt\reporter` 그린필드 → src/ 트리·테스트·문서 모두 빌드 + GitHub 공개 레포 연결 + 매시간 자동 갱신 셋업.

**오늘 마지막 산출물**:
- `data/output/329180/2026-05-08.html` (재빌드, 자동 피어로)
- `data/output/456160/2026-05-08.html` (신규 — 지투지바이오)
- GitHub: `https://github.com/bizsinsightclub/stockreport`
- (Pages 활성화 후) `https://bizsinsightclub.github.io/stockreport/`

| 섹션 | 데이터 출처 | 상태 |
|---|---|---|
| 헤더 가격·시그널 카드 | pykrx | ✅ |
| §1 시세 차트 (121거래일 OHLC + MA) | pykrx `get_market_ohlcv_by_date` | ✅ |
| §1.5 수급 차트 (외/기/개 일별 순매수) | pykrx `get_market_trading_value_by_date` | ✅ |
| §3 기술 차트 (RSI/MACD/Bollinger) | analyzers/price | ✅ |
| §4 공시 | DART OpenAPI `list.json` | ✅ |
| §5 분기별 실적 (억원·2자리·바위값) | DART OpenAPI `fnlttSinglAcntAll.json` | ✅ |
| §6 피어 비교 (자동 선정 4종목) | **DART induty_code prefix 매칭** | ✅ |
| §7 거시 USD/KRW (125일) | Frankfurter API (ECB) | ✅ |
| 검증 배지 | validators/numbers.py v2 | ⚠ unmatched ~16% (analyzer 파생값) |

**자동 피어 매칭 검증 완료**:
- 329180 HD현대중공업 (induty 31113, 4자리 prefix `3111`)
  → 042660 한화오션 / 010140 삼성중공업 / 439260 대한조선 / 075580 세진중공업
- 456160 지투지바이오 (induty 21212, 3자리 prefix `212`)
  → 000250 삼천당제약 / 237690 에스티팜 / 068760 셀트리온제약 / 039200 오스코텍

## 2. 환경 상태

- **Python**: 3.11.9
- **의존성**: 12개 (`requirements.txt`) — `holidays>=0.40` 추가
- **`.env`**: 4개 키 (KRX_API_KEY, DART_API_KEY, KRX_ID, KRX_PW)
- **Git**: 레포 초기화 완료, origin = `https://github.com/bizsinsightclub/stockreport`, branch `main`, 첫 push 성공
- **자동화**: `scripts/hourly.ps1` 작성 완료 (평일 09–16시 KST + 한국 공휴일 스킵)

## 3. 다음 세션 우선순위

### A. ✅ 자동 피어 선정 — 완료 (2026-05-09)
DART `company.json` 의 KSIC induty_code prefix 매칭으로 해결. 5→4→3자리 단계 확장 + 시총 상위 250 풀 + 24h 캐시 (`data/cache/induty_code.json`). KRX OpenAPI 401 / pykrx 사이트 변경 버그 모두 우회. 코드: `src/collectors/dart_openapi.py:fetch_company`, `src/meta/peers.py:_try_dart_induty`.

### B. 검증기 unmatched 줄이기 (다음 우선)

**현상**: 검증 배지가 `fail` (329180: 14/85≈16%, 456160: 13/76≈17%). 미매칭 사례 대부분이 RSI/52주 위치 같은 **analyzer 파생값**. raw JSON 에 원본 시세만 있고 계산값이 없어서 정상값임에도 unmatched.

**해결**: `validators/numbers.py` 가 multiset 에 raw JSON 외 `enriched_price` (analyzer 출력) 의 numeric leaves 도 포함하도록 확장. main.py 에서 `enriched_price` 를 `_enriched.json` 으로 raw_dir 에 저장하면 검증기가 자연 인식. 또는 validator API 에 `extra_sources` 인자 추가.

목표: unmatched <5% → fail → ok 배지.

### C. 수급 차트 시각화 점검

수급 raw JSON 은 121일 일별 시계열 정상이지만 `chart_builder.flow_chart` 가 어떤 컬럼을 메인으로 쓰는지 확인 필요. 외국인합계 누적순매수 라인이 메인이 되도록 `renderer/charts.py` 의 flow 차트 부분 점검.

### D. (있다면) Phase 2 진입 준비

`/report-stock` 슬래시 커맨드 + 세션 LLM 코멘트 + claim-level citation. 슬롯 6개(brief, s1_price, s2_tech, s3_disc_*, s4_peer, s4_macro)는 이미 템플릿에 마킹되어 있음. plan: `C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md` §3, §4.

## 4. 사용자가 직접 할 것 (다음 세션 시작 전)

### 4.1 작업 스케줄러 등록 (1줄, 관리자 PowerShell)
```powershell
schtasks /create /sc HOURLY /tn "KRX_Reporter" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\pjt\reporter\scripts\hourly.ps1" /st 09:00 /f
```
확인: `schtasks /query /tn "KRX_Reporter"`. 수동 테스트: `powershell -File C:\pjt\reporter\scripts\hourly.ps1`.

### 4.2 GitHub Pages 활성화 (브라우저)
1. https://github.com/bizsinsightclub/stockreport/settings/pages
2. Source: Deploy from a branch
3. Branch: `main` / `(root)`
4. Save → 1–2분 후 `https://bizsinsightclub.github.io/stockreport/` 살아남

### 4.3 ⚠ 보안 — `KRX_PW` 변경
어제 채팅 기록에 `KRX_PW=matchbox20!` 평문 노출. data.krx.co.kr 비밀번호 변경 + `.env` 의 `KRX_PW` 값 갱신.

## 5. 빠른 재개 명령어

```powershell
# (1) 환경 확인
py -3.11 --version             # 3.11.9 expected
Get-Content C:\pjt\reporter\.env | Select-String "KRX_ID|KRX_PW|DART|KRX_API"

# (2) 어제 빌드 결과 다시 열기
Invoke-Item C:\pjt\reporter\data\output\329180\2026-05-08.html
Invoke-Item C:\pjt\reporter\data\output\456160\2026-05-08.html

# (3) 새 빌드 (자동 피어 적용 — --peers 생략)
Set-Location C:\pjt\reporter
py -3.11 -m src.main 329180 --date 2026-05-08
py -3.11 -m src.main 456160 --date 2026-05-08

# (4) 자동화 수동 트리거 (테스트)
powershell -File C:\pjt\reporter\scripts\hourly.ps1

# (5) 검증 배지 상세
Get-Content C:\pjt\reporter\data\output\329180\2026-05-08.validation.json -Raw
```

## 6. 오늘(2026-05-09) 새로 만진 파일

- `src/collectors/dart_openapi.py` — `fetch_company`, `lookup_induty_code`, `bulk_lookup_induty_codes` 추가 (24h 캐시: `data/cache/induty_code.json`)
- `src/meta/peers.py` — `_try_dart_induty`, `_detect_market` 추가. `auto_select` 호출 순서: KRX OpenAPI → DART induty → pykrx 시총
- `scripts/hourly.ps1` — 신규. 평일 09–16시 KST + 휴장일 스킵 + git push
- `index.html` (root) — `data/output/` 으로 redirect (Pages 루트용)
- `.gitignore` — `.omc/`, `.claude/`, `data/cache/`, `*.validation.json`, `logs/` 추가, `data/output/` 은 push 대상으로 변경
- `requirements.txt` — `holidays>=0.40` 추가
- `CLAUDE.md` §7 — 자동화 운영 절(GitHub Actions cron 미사용 / 로컬 schtasks + Pages / secrets) 갱신
- `HANDOFF.md` §2 — 의사결정 표에 자동화 + 자동 피어 항목 추가

## 7. 알려진 미해결 / 메모

- **KRX OpenAPI 401**: 키 자체는 유효하나 `stk_bydd_trd` 등 개별 API 구독 승인이 portal 에서 필요. https://openapi.krx.co.kr → My Page → 신청 현황. (DART induty 우회로 자동 피어는 해결됨, 하지만 KRX OpenAPI 가 풀리면 더 정확한 IDX_IND_CD 매칭이 1순위로 사용됨.)
- **검증기 false-positive**: §3.B 참조. RSI/52주 같은 파생값이 unmatched 로 잡힘.
- **Phase 2 LLM 정책**: `CLAUDE.md` §0.3 / §3.3 의 "LLM 미사용" 표현은 Phase 2 진입 시 갱신 예정.
- **`KRX_PW` 평문 노출**: §4.3 처리 필요.
- **자동 피어 첫 실행 비용**: 시총 상위 250개 induty_code 첫 호출 시 30–60초. 이후 24h 캐시. 매시간 자동 빌드는 캐시 적중하므로 빠름.

## 8. plan 파일 위치 (Phase 2 설계 참조)

`C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md`

LLM 슬롯 6개의 정확한 위치, citation 검증기 스펙, Phase 2 진입 시 CLAUDE.md §0.3/§3.3 갱신 항목 모두 들어 있음.
