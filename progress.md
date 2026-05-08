# 진행 상황 — 2026-05-09

> 다음 세션에 이 파일을 먼저 읽고 §1 "현재 상태"와 §3 "다음 세션 우선순위"부터 보면 됩니다.

## 1. 현재 상태 (Phase 1 코어 ✅ 완료, 데이터 파이프라인 대부분 동작)

`C:\pjt\reporter` 그린필드에서 시작해서 src/ 트리·테스트·문서 모두 빌드. `python -m src.main 329180 --date 2026-05-08` 으로 실데이터 빌드 동작 확인.

**오늘 마지막 산출물**: `data/output/329180/2026-05-08.html` (139 KB)

| 섹션 | 데이터 출처 | 상태 |
|---|---|---|
| 헤더 가격·시그널 카드 (MA/RSI/MACD/Bollinger/52주위치) | pykrx | ✅ |
| §1 시세 차트 (121거래일 OHLC + MA) | pykrx `get_market_ohlcv_by_date` | ✅ |
| §1.5 수급 차트 (외인·기관·개인·기타법인 일별 순매수, 121일) | pykrx `get_market_trading_value_by_date` | ✅ |
| §3 기술 차트 (RSI/MACD/Bollinger) | analyzers/price | ✅ |
| §4 공시 (14건) | DART OpenAPI `list.json` | ✅ |
| §5 분기별 실적 (5분기, **억원·2자리·바위값표기**) | DART OpenAPI `fnlttSinglAcntAll.json` | ✅ |
| §6 피어 비교 (4종목 6M 정규화) | pykrx 시세 + `--peers` 수동 지정 | ⚠ 자동선정 미완 |
| §7 거시 USD/KRW (125일) | Frankfurter API (ECB 무료) | ✅ |
| 검증 배지 | validators/numbers.py v2 | ⚠ unmatched 15 (대부분 analyzer 파생값) |

## 2. 환경 상태

- **Python**: 3.11.9 (winget Python.Python.3.11)
- **의존성**: `requirements.txt` 11개 모두 설치 완료 (`py -3.11 -m pip install -r requirements.txt`)
- **`.env`**: 4개 키 등록
  - `KRX_API_KEY` — KRX OpenAPI (HTTP 401: API별 추가 승인 필요)
  - `DART_API_KEY` — DART OpenAPI ✅ 정상
  - `KRX_ID`, `KRX_PW` — data.krx.co.kr 로그인 자격증명 ✅ pykrx 인증 통과 (⚠ 비번 채팅 노출됨 — 변경 권장)

## 3. 다음 세션 우선순위

### A. 자동 피어 선정의 섹터 매칭 (가장 효과 큼)

**현상**: `--peers` 미지정 시 시총 상위(005930 삼성전자, 000660 SK하이닉스 등)가 잡혀 조선업 피어가 안 나옴. `meta/peers.py`의 `_try_pykrx`가 `get_market_sector_classifications`로 섹터 매핑을 시도하는데 KRX 사이트 변경 영향으로 실패하는 듯.

**옵션**:
1. **KRX OpenAPI `stk_isu_base_info` 활용** (포털에서 401 해제 후) — `IDX_IND_NM`/`IDX_IND_CD` 컬럼으로 종목→섹터 매핑. 이미 `meta/peers.py:_try_krx_openapi`가 시도하지만 401로 막혀있음. KRX OpenAPI 포털에서 다음 API 추가 신청·승인 필요:
   - 유가증권 일별매매정보 (`stk_bydd_trd`)
   - 코스닥 일별매매정보 (`ksq_bydd_trd`)
   - 유가증권 종목기본정보 (`stk_isu_base_info`)
   승인되면 코드 수정 없이 자동 피어 선정 동작.
2. **pykrx의 `get_market_sector_classifications` 디버그** — KRX_ID/PW로 인증된 상태이므로 실제 호출해서 무엇이 반환되는지 확인. 컬럼명·인덱스 변경됐으면 `meta/peers.py:_try_pykrx`의 `same = sector_df[sector_df["업종코드"] == ...]` 부분 수정.
3. **하드코딩 섹터 매핑 테이블** (`config.py`에 SECTOR_MAP_BY_TICKER 추가) — 임시 우회. 조선/반도체/자동차 핵심 종목만 손으로 매핑.

권장: 1번 (KRX 포털 추가 신청) → 안 되면 2번 디버그.

### B. 검증기 unmatched 줄이기

**현상**: 검증 배지가 `fail` (15/82, ≈18%). 미매칭 사례 대부분이 `61.2`(RSI), `86.2%`(52주 위치) 같은 **analyzer 파생값**. raw JSON에는 원본 시세만 있고 RSI/MA/52주 같은 계산값이 없어서 정상값임에도 unmatched로 잡힘.

**해결**: `validators/numbers.py`가 multiset에 raw JSON 외에도 `enriched_price` (analyzer 출력)의 numeric leaves도 추가하도록 확장. main.py에서 `enriched_price` 직렬화해 raw_dir 옆에 `_enriched.json`으로 저장하면 검증기가 자연스럽게 인식. 또는 validator API에 `extra_sources` 인자 추가.

목표: unmatched <5%로 떨어뜨려 fail → ok 배지.

### C. 수급 차트 시각화 점검

수급 raw JSON은 121일 일별 시계열이 정상이지만 `chart_builder.flow_chart`가 어떤 컬럼을 쓰는지 확인 필요. 외국인합계 누적순매수 라인이 메인이 되도록 `renderer/charts.py`의 flow 차트 부분 확인.

### D. (있다면) Phase 2 진입 준비

`/report-stock` 슬래시 커맨드 + 세션 LLM 코멘트 + claim-level citation. 슬롯 6개(brief, s1_price, s2_tech, s3_disc_*, s4_peer, s4_macro)는 이미 템플릿에 마킹되어 있음. plan 파일(`C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md`) §3, §4에 설계 있음.

## 4. 빠른 재개 명령어

```powershell
# (1) 환경 확인
py -3.11 --version             # 3.11.9 expected
Get-Content C:\pjt\reporter\.env | Select-String "KRX_ID|KRX_PW|DART|KRX_API"

# (2) 어제 빌드 결과 다시 열기
Invoke-Item C:\pjt\reporter\data\output\329180\2026-05-08.html

# (3) 새 빌드 (오늘 날짜 기준 직전 거래일로)
Set-Location C:\pjt\reporter
py -3.11 -m src.main 329180 --date 2026-05-08
# 또는 자동 피어 우회용:
py -3.11 -m src.main 329180 --date 2026-05-08 --peers "010140,042660,010620,064350"

# (4) 다른 종목 테스트 (일반화 검증)
py -3.11 -m src.main 005930 --date 2026-05-08 --peers "000660,066570,034220,402340"

# (5) 검증 배지 상세
Get-Content C:\pjt\reporter\data\output\329180\2026-05-08.validation.json -Raw
```

## 5. 오늘 만진 핵심 파일

- `src/main.py` — orchestration. 오늘 추가/수정: `load_dotenv()`, `_safe_fetch_flow` (KRX OpenAPI 시도 제거 → pykrx 단독), `_normalize_financial_records`, KST 타임존
- `src/collectors/dart_openapi.py` — `fetch_financials_annual/quarterly`, `lookup_corp_code` (24h 디스크 캐시: `data/cache/corp_code.json`)
- `src/collectors/krx_openapi.py` — `stk_bydd_trd` 등 실 엔드포인트 구현 (포털 승인 대기 중)
- `src/collectors/macro.py` — Frankfurter (ECB) USD/KRW
- `src/fallbacks/pykrx_price.py` — `fetch_investor_flow`를 `get_market_trading_value_by_date`로 (일별 시계열)
- `src/analyzers/flow.py` — `_INVESTOR_COLS`에 `기관합계`/`외국인합계`/`기타법인` 추가, `_FOREIGN_COL_PRIORITY` 도입
- `src/renderer/charts.py` — `financials_bars` 억원 변환 + 2자리 소수점 + period 짧은 라벨 + 바위 값 표기
- `src/cli.py` — `--skip-llm` flag default 제거 (정상 store_true)
- `CLAUDE.md`, `HANDOFF.md` — Phase 1 새 구조 반영
- `.env` — 4개 키
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `tests/*` — Phase 1 빌드

## 6. 알려진 미해결 / 메모

- **KRX OpenAPI 401**: 키 자체는 유효하나 `stk_bydd_trd` 등 개별 API에 대한 구독 승인이 portal에서 필요. https://openapi.krx.co.kr → My Page → 신청 현황 점검.
- **KRX OpenAPI 카탈로그에 투자자별 매매 API 없음**: 사용자가 보내준 전체 카탈로그 확인 결과(지수/주식/증권상품/채권/파생상품/일반상품/ESG 7개 카테고리), 종목별 외/기/개 일별 매매 데이터는 KRX OpenAPI 영역 밖. → pykrx + KRX_ID/KRX_PW 경로가 유일하게 동작 중.
- **`KRX_PW` 평문 노출**: 작업 중 채팅에 노출됨. data.krx.co.kr 비번 변경 + `.env` 동기화 필요.
- **자동 피어가 시총 상위로 degrade**: §3.A 참조.
- **`24 FY` 라벨**: 분기 정렬은 `2024-FY`(4분기 위치) > `2025-Q1` > `2025-Q2` > `2025-Q3` > `2025-FY` 순으로 표시되는데, 25 FY는 아직 사업보고서 미공개일 수 있어 데이터 출처(보고서 종류) 검증 한 번 권장.
- **검증기 false-positive**: §3.B 참조.

## 7. plan 파일 위치 (Phase 2 설계 참조)

`C:\Users\User\.claude\plans\claude-md-handoff-md-fancy-pinwheel.md`

LLM 슬롯 6개의 정확한 위치, citation 검증기 스펙, Phase 2 진입 시 CLAUDE.md §0.3/§3.3 갱신 항목 모두 들어 있음.
