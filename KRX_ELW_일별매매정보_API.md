# KRX ELW 일별매매정보 API

## 개요

- **API 명**: ELW 일별매매정보
- **설명**: ELW(주식워런트증권)의 매매정보 제공
- **데이터 제공 시작일**: 2010년 01월 04일
- **Endpoint URL**: `https://data-dbg.krx.co.kr/svc/apis/etp/elw_bydd_trd`

---

## Request

### InBlock_1

| Name | Type | Description |
| --- | --- | --- |
| basDd | string | 기준일자 |

### Request Sample

```json
{"basDd":"__"}
```

---

## Response

### OutBlock_1

| Name | Type | Description |
| --- | --- | --- |
| BAS_DD | string | 기준일자 |
| ISU_CD | string | 종목코드 |
| ISU_NM | string | 종목명 |
| TDD_CLSPRC | string | 종가 |
| CMPPREVDD_PRC | string | 대비 |
| TDD_OPNPRC | string | 시가 |
| TDD_HGPRC | string | 고가 |
| TDD_LWPRC | string | 저가 |
| ACC_TRDVOL | string | 거래량 |
| ACC_TRDVAL | string | 거래대금 |
| MKTCAP | string | 시가총액 |
| LIST_SHRS | string | 상장증권수 |
| ULY_NM | string | 기초자산_자산명 |
| ULY_PRC | string | 기초자산_종가 |
| CMPPREVDD_PRC_ULY | string | 기초자산_대비 |
| FLUC_RT_ULY | string | 기초자산_등락률 |

### Response Sample

```json
{
  "OutBlock_1": [
    {
      "BAS_DD": "__",
      "ISU_CD": "__",
      "ISU_NM": "__",
      "TDD_CLSPRC": "-",
      "CMPPREVDD_PRC": "-",
      "TDD_OPNPRC": "-",
      "TDD_HGPRC": "-",
      "TDD_LWPRC": "-",
      "ACC_TRDVOL": "-",
      "ACC_TRDVAL": "-",
      "MKTCAP": "-",
      "LIST_SHRS": "-",
      "ULY_NM": "-",
      "ULY_PRC": "-",
      "CMPPREVDD_PRC_ULY": "-",
      "FLUC_RT_ULY": "-"
    }
  ]
}
```
