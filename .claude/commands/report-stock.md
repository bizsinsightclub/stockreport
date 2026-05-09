---
description: KRX 종목의 LLM 슬롯 6개를 작성하고 citation 포함 사이드카로 저장 후 빌드 검증
---

당신은 환각 없는 한국 주식 리포트 시스템(`C:\pjt\reporter`)의 LLM 코멘트 작성자입니다.

입력 ticker: **$ARGUMENTS**

## 절차

### 1. 빌드로 raw 데이터 갱신

```
cd C:/pjt/reporter
py -3.11 -m src.main $ARGUMENTS
```

빌드 로그에서 발행 기준일(`as_of` / `--date` 인자 또는 today)을 확인합니다. 이 날짜를 `{date}`로 부르겠습니다 (`YYYY-MM-DD` ISO).

### 2. raw / derived 파일 읽기

`data/raw/{date}/$ARGUMENTS_*.json`:

- `_price.json` — OHLCV records
- `_flow.json` — 외/기/개 일별 순매수
- `_disclosures.json` — DART 공시 list
- `_financials.json` — 분기 재무 records
- `_enriched.json` — analyzer 파생 (signals, header, peer_rows, macro_cards). citation 의 핵심 출처

### 3. 슬롯 6개 작성 (한국어, 사실 기반)

| Slot | 분량 | 내용 |
|---|---|---|
| `brief` | 1–2 문장 | 헤더 한 줄 요약 — 가격, 등락률, 외국인 동향 등 |
| `s1_price` | 1–2 문장 | 거래대금 / 유동성 관전 포인트 |
| `s2_tech` | 1–2 문장 | RSI / MACD / Bollinger 시그널 해석 |
| `s3_disc_0`, `s3_disc_1`, … | 1 문장 | 각 공시 행 한 줄 평. 공시 개수만큼 작성 (인덱스는 `disclosures` 배열 순서) |
| `s4_peer` | 2–3 문장 | 피어 비교 인사이트 — 정규화 수익률, 시총 위치 등 |
| `s4_macro` | 1–2 문장 | USD/KRW 등 거시 한 줄 평 |

원칙:
- 정성적 표현(예: "강세 추세 유지")은 자유, **모든 숫자는 raw 출처에 정확히 일치해야 한다**.
- 환각 없음. 추측한 수치는 절대 쓰지 않는다.
- citation 의 `value` 는 raw 파일에서 직접 확인한 값만.
- `token` 은 raw_text 안에 등장하는 정확한 substring (예: `"+3.20%"` 와 `"3.2%"` 는 다름).

### 4. Citation 형식

각 numeric token 마다:

```json
{
  "token": "61.2",
  "file": "$ARGUMENTS_enriched.json",
  "path": "data.signals.rsi",
  "value": 61.2
}
```

- `file`: `data/raw/{date}/` 안의 파일명 (확장자 포함)
- `path`: dot-separated json path. 리스트 인덱스는 정수로 (예: `data.0.종가`)
- `value`: raw 파일에서 path 따라간 실제 값

자주 쓰는 path:
- 가격, 등락률 → `$ARGUMENTS_enriched.json` 의 `data.header.price_now` / `data.header.change_pct`
- RSI, 52주 위치 → `data.signals.rsi` / `data.signals.week52_pos`
- 피어 시총·수익률 → `data.peer_rows.{i}.market_cap_oku` / `data.peer_rows.{i}.return_180d`
- 거시 USD/KRW → `data.macro_cards.0.value` / `data.macro_cards.0.delta`
- 공시 개별 → `$ARGUMENTS_disclosures.json` 의 `data.{i}.{필드}`
- 분기 매출/영업이익 → `$ARGUMENTS_financials.json` (정규화된 record), 또는 `_enriched.json` 안의 financials 가 있으면 거기

### 5. 사이드카 저장

`data/llm/$ARGUMENTS/{date}.json`:

```json
{
  "ticker": "$ARGUMENTS",
  "as_of": "{date}",
  "generated_at": "<ISO 8601 KST>",
  "slots": {
    "brief": {
      "raw_text": "...",
      "citations": [{"token": "...", "file": "...", "path": "...", "value": ...}, ...]
    },
    "s1_price": {...},
    "s2_tech": {...},
    "s3_disc_0": {...},
    "s4_peer": {...},
    "s4_macro": {...}
  }
}
```

### 6. 재빌드 + 검증

```
py -3.11 -m src.main $ARGUMENTS
```

`data/output/$ARGUMENTS/{date}.html` 의 두 검증 배지 모두 `pass` 인지 확인:

- 숫자 대조 (`numbers`): pass
- Citation 검증 (`citations`): pass

`citations.unmatched > 0` 이면 `data/output/$ARGUMENTS/{date}.citations.json` 의 `examples_mismatched` / `examples_uncited` 보고 사이드카 (raw_text 또는 citations) 를 고친 후 재빌드.

### 7. 사용자 보고

- HTML 출력 경로
- 두 검증 배지 상태 (둘 다 pass 가 목표)
- 사이드카 경로
