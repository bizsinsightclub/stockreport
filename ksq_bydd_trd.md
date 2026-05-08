# 코스닥 일별매매정보 API

> KRX OpenAPI — 코스닥시장(KOSDAQ) 일별 매매정보 조회
> **본 프로젝트에서는 보조 데이터** (HD현대중공업은 KOSPI이지만, 조선업 관련 코스닥 부품·기자재 종목 비교 시 활용 가능)

## 개요

| 항목 | 값 |
|---|---|
| 데이터 범위 | 코스닥시장(KOSDAQ) 상장 주권 전체 |
| 데이터 시작일 | 2010-01-04 |
| 응답 단위 | 1일 (해당 기준일의 전 종목 일괄 반환) |
| Endpoint | `https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd` |
| 인증 | KRX OpenAPI Key (HTTP Header) |

## 요청 (Request)

### InBlock_1

| 파라미터 | 타입 | 필수 | 설명 | 형식 |
|---|---|---|---|---|
| `basDd` | string | ✅ | 기준일자 | `YYYYMMDD` (예: `20260508`) |

### Request 예시

```json
{ "basDd": "20260508" }
```

### 헤더 (KRX OpenAPI 표준)

```
Content-Type: application/json
AUTH_KEY: <KRX_API_KEY>
```

## 응답 (Response)

### OutBlock_1

| 필드 | 타입 | 설명 | 비고 |
|---|---|---|---|
| `BAS_DD` | string | 기준일자 | `YYYYMMDD` |
| `ISU_CD` | string | 종목코드 | 6자리 |
| `ISU_NM` | string | 종목명 | 한글 |
| `MKT_NM` | string | 시장구분 | "KOSDAQ" 등 |
| `SECT_TP_NM` | string | 소속부 | 코스닥은 "벤처기업부", "중견기업부", "기술성장기업부" 등 구분 존재 |
| `TDD_CLSPRC` | string | 종가 | 천단위 콤마 포함 가능 |
| `CMPPREVDD_PRC` | string | 전일 대비 | 음수 가능 |
| `FLUC_RT` | string | 등락률 (%) | 소수점 포함 |
| `TDD_OPNPRC` | string | 시가 | |
| `TDD_HGPRC` | string | 고가 | |
| `TDD_LWPRC` | string | 저가 | |
| `ACC_TRDVOL` | string | 거래량 | 주식 수 |
| `ACC_TRDVAL` | string | 거래대금 | 원 |
| `MKTCAP` | string | 시가총액 | 원 |
| `LIST_SHRS` | string | 상장주식수 | 주식 수 |

> **주의**: 모든 숫자 필드는 string 타입으로 반환된다. 콤마(`,`) 구분자가 들어있을 수 있으므로 `str.replace(",", "")` 후 `int`/`float` 변환 필요. 결측값은 `"-"`로 표기됨.

### Response 예시 (형식)

```json
{
  "OutBlock_1": [
    {
      "BAS_DD": "20260508",
      "ISU_CD": "...",
      "ISU_NM": "...",
      "MKT_NM": "KOSDAQ",
      "SECT_TP_NM": "...",
      "TDD_CLSPRC": "...",
      "CMPPREVDD_PRC": "...",
      "FLUC_RT": "...",
      "TDD_OPNPRC": "...",
      "TDD_HGPRC": "...",
      "TDD_LWPRC": "...",
      "ACC_TRDVOL": "...",
      "ACC_TRDVAL": "...",
      "MKTCAP": "...",
      "LIST_SHRS": "..."
    }
  ]
}
```

## 유가증권 API와의 관계

스키마와 파라미터, 호출 방식 모두 **유가증권 API(`stk_bydd_trd`)와 동일**. 차이는:

- **Endpoint**: `ksq_bydd_trd` (코스닥) vs `stk_bydd_trd` (유가증권)
- **응답의 `MKT_NM`**: "KOSDAQ" vs "KOSPI"
- **`SECT_TP_NM`**: 코스닥은 소속부 분류가 더 다양함 (벤처기업부, 중견기업부 등)

따라서 collector 구현 시 **공통 함수 + market 파라미터**로 처리하는 게 효율적:

```python
# 예시 시그니처
def fetch_bydd_trd(bas_dd: str, market: Literal["kospi", "kosdaq"]) -> dict:
    endpoint_map = {
        "kospi":  "stk_bydd_trd",
        "kosdaq": "ksq_bydd_trd",
    }
    ...
```

## 본 프로젝트에서의 활용

### 사용 시나리오 (보조)
HD현대중공업 자체는 KOSPI 종목이라 직접적으로는 사용 빈도가 낮지만, 다음 확장 시나리오에서 필요해진다:

1. **조선 기자재 협력사 비교** — 코스닥 상장 조선 부품·기자재 종목과의 동조성 분석
   - 예: 케이씨씨글라스, 세진중공업, 한국카본, 인화정공 등 (실제 편입 시 상장 시장 재확인 필요)
2. **조선업 산업 전반 모멘텀** — 조선업 코스닥 종목들의 평균 등락률을 산업 심리 지표로 활용
3. **시장 대비 상대 성과** — 같은 날 KOSDAQ 평균 등락률 대비 HD현대중공업 변동률

### 본 프로젝트의 우선순위
**낮음 (Phase 2-3에서 검토)**. Phase 1 단계에서는 KOSPI API만 통합하면 충분.

## 통합 위치 (TODO)

- [ ] `src/collectors/krx_bydd.py`에서 KOSPI/KOSDAQ 통합 처리 (시장 파라미터로 분기)
- [ ] 코스닥 활용 시점에 `config.py`의 `PEERS` 리스트에 코스닥 종목 추가
- [ ] 시장구분 정보를 시그널 카드/피어 테이블에 표기

## 참조

- KRX OpenAPI 포털: https://openapi.krx.co.kr
- 같은 시리즈 API: [`stk_bydd_trd.md`](./stk_bydd_trd.md) (유가증권시장)
