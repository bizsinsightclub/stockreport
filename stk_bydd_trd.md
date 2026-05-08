# 유가증권 일별매매정보 API

> KRX OpenAPI — 유가증권시장(KOSPI) 일별 매매정보 조회
> **본 프로젝트의 메인 시세 데이터 소스** (HD현대중공업 329180은 KOSPI 종목)

## 개요

| 항목 | 값 |
|---|---|
| 데이터 범위 | 유가증권시장(KOSPI) 상장 주권 전체 |
| 데이터 시작일 | 2010-01-04 |
| 응답 단위 | 1일 (해당 기준일의 전 종목 일괄 반환) |
| Endpoint | `https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd` |
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
| `MKT_NM` | string | 시장구분 | "KOSPI" 등 |
| `SECT_TP_NM` | string | 소속부 | 예: "관리종목", "투자주의" 등 (해당 없으면 "-") |
| `TDD_CLSPRC` | string | 종가 | 천단위 콤마 포함 가능, 숫자 변환 필요 |
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
      "ISU_CD": "329180",
      "ISU_NM": "HD현대중공업",
      "MKT_NM": "KOSPI",
      "SECT_TP_NM": "-",
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

## 본 프로젝트에서의 활용

### 사용 시나리오
1. **메인 시세 collector** — `korea-stock-mcp` MCP 호출이 실패할 경우의 1차 fallback
2. **개별 종목 검색** — 응답에서 `ISU_CD == "329180"` 필터링하여 HD현대중공업 행 추출
3. **피어 비교** — 같은 응답에서 `009540` (HD한국조선해양) 동시 추출 가능 (KOSPI 한정)

### 주의: 단일 종목 직접 조회 불가
이 API는 **기준일자별 전 종목 일괄 응답** 구조다. 특정 종목의 기간 시세를 얻으려면:
- 영업일별로 N회 호출 (180일 = 약 120회) → 일별 응답에서 종목 필터링
- 또는 영업일별로 받은 전 종목을 누적 저장한 뒤 해당 종목만 필터

이는 호출량이 많기 때문에 본 프로젝트에서는 **주력 경로를 `korea-stock-mcp`(또는 pykrx)로 두고**, KRX OpenAPI는 데이터 검증·교차 확인용으로만 쓰는 것이 합리적이다.

### 코스닥 API와의 차이
없음. `MKT_NM` 값과 endpoint URL만 다르고 스키마/파라미터/응답 구조 모두 동일하다 (`./ksq_bydd_trd.md` 참조).

## 통합 위치 (TODO)

- [ ] `src/collectors/krx_bydd.py` 신규 생성 (직접 HTTP 호출)
- [ ] `src/config.py`에 endpoint 상수 추가
- [ ] `.env.example`의 `KRX_API_KEY` 주석에 본 API 신청이 필요함 명시
- [ ] `main.py`에서 MCP 호출 실패 시 이 collector로 fallback

## 참조

- KRX OpenAPI 포털: https://openapi.krx.co.kr
- 일자별 데이터 시작: 2010-01-04
- 호출 한도: KRX 정책 확인 필요 (계정별 일일 호출 제한 존재)
