"""ETF / ETN / ELW 시장 전반 분석.

순수 함수 — 외부 호출 없음 (CLAUDE.md §2). 입력은 KRX OpenAPI / pykrx 가
반환한 row list (둘 다 컬럼 형식 통일하여 처리).

거래대금 상위 N + 운용사별 합계 + 등락 분포 등 시장 흐름 metric 추출.
"""

from __future__ import annotations

from typing import Any

# ─── ETF 운용사 매핑 ─────────────────────────────────────────────────
# ETF 종목명 prefix 로 운용사 식별. 한국 ETF 시장 주요 11 사 + 기타.
_ETF_BRAND_TO_AMC: list[tuple[str, str]] = [
    ("KODEX", "삼성자산운용"),
    ("TIGER", "미래에셋자산운용"),
    ("ACE", "한국투자신탁운용"),
    ("KINDEX", "한국투자신탁운용"),
    ("PLUS", "한화자산운용"),
    ("ARIRANG", "한화자산운용"),
    ("SOL", "신한자산운용"),
    ("KBSTAR", "KB자산운용"),
    ("KOSEF", "키움투자자산운용"),
    ("HANARO", "NH-Amundi자산운용"),
    ("히어로즈", "키움투자자산운용"),
    ("1Q", "하나자산운용"),
    ("BNK", "BNK자산운용"),
    ("WOORI", "우리자산운용"),
    ("TIMEFOLIO", "타임폴리오자산운용"),
    ("파워", "교보악사자산운용"),
    ("HK", "흥국자산운용"),
    ("마이티", "다올자산운용"),
    ("BIG", "DB자산운용"),
    ("WON", "WON자산운용"),
]


def detect_etf_amc(name: str) -> str:
    """ETF 종목명에서 운용사 추출. 매칭 실패 시 '기타'."""
    if not name:
        return "기타"
    upper = name.upper().strip()
    for brand, amc in _ETF_BRAND_TO_AMC:
        if upper.startswith(brand.upper() + " ") or upper.startswith(brand.upper()):
            return amc
    return "기타"


# 인터랙티브 대시보드용 임베드 행 수 — ELW 만 cap (2700+ → 거래대금 상위 N).
# ETF/ETN 은 전수 (각각 ~1100 / ~400) — 클라이언트 필터가 의미 있으려면 전수가 좋다.
_ELW_DASHBOARD_ROWS: int = 300


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        s = str(v).replace(",", "").strip()
        if not s or s == "-":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_row(r: dict[str, Any]) -> dict[str, Any]:
    """KRX OpenAPI / pykrx ETF row → 통일 dict.

    ``isu_cd, isu_nm, open, high, low, close, volume, traded_value,
    market_cap, list_shrs, nav, base_index_name, base_index_close, fluc_rt``
    """
    return {
        "isu_cd": str(r.get("ISU_CD") or r.get("ticker") or "").strip(),
        "isu_nm": str(r.get("ISU_NM") or r.get("name") or "").strip(),
        "open": _to_float(r.get("TDD_OPNPRC") or r.get("시가")),
        "high": _to_float(r.get("TDD_HGPRC") or r.get("고가")),
        "low": _to_float(r.get("TDD_LWPRC") or r.get("저가")),
        "close": _to_float(r.get("TDD_CLSPRC") or r.get("종가")),
        "volume": _to_float(r.get("ACC_TRDVOL") or r.get("거래량")),
        "traded_value": _to_float(r.get("ACC_TRDVAL") or r.get("거래대금")),
        "market_cap": _to_float(r.get("MKTCAP") or r.get("시가총액")),
        "list_shrs": _to_float(r.get("LIST_SHRS") or r.get("상장주식수")),
        "nav": _to_float(r.get("NAV")),
        "fluc_rt": _to_float(r.get("FLUC_RT") or r.get("등락률")),
        "base_index_name": str(r.get("IDX_IND_NM") or r.get("기초지수") or "").strip(),
        "base_index_close": _to_float(r.get("OBJ_STKPRC_IDX") or r.get("기초지수_종가")),
        "base_index_fluc": _to_float(r.get("FLUC_RT_IDX")),
        "uly_nm": str(r.get("ULY_NM") or "").strip(),  # ELW 기초자산
    }


def analyze_etp_market(rows: list[dict[str, Any]], *, kind: str, top_n: int = 30) -> dict[str, Any]:
    """ETP 시장 row list → 분석 dict.

    Returns:
        ``count, total_traded_oku, gainers, losers, unchanged,
          top_by_traded, by_amc (ETF only), as_of``
    """
    out: dict[str, Any] = {
        "kind": kind,
        "count": 0,
        "total_traded_oku": None,
        "total_market_cap_oku": None,
        "gainers": 0,
        "losers": 0,
        "unchanged": 0,
        "top_by_traded": [],
        "by_amc": [],
        "rows": [],
        "as_of": None,
    }
    if not rows:
        return out

    norm = [_normalize_row(r) for r in rows]
    norm = [n for n in norm if n["isu_cd"]]
    out["count"] = len(norm)
    if not norm:
        return out

    out["as_of"] = next((r.get("BAS_DD") for r in rows if r.get("BAS_DD")), None)
    if out["as_of"] and len(out["as_of"]) == 8:
        out["as_of"] = f"{out['as_of'][:4]}-{out['as_of'][4:6]}-{out['as_of'][6:8]}"

    total_tv = sum((n["traded_value"] or 0) for n in norm)
    total_mc = sum((n["market_cap"] or 0) for n in norm)
    out["total_traded_oku"] = round(total_tv / 1e8, 1)
    out["total_market_cap_oku"] = round(total_mc / 1e8, 1)

    for n in norm:
        f = n["fluc_rt"] or 0
        if f > 0:
            out["gainers"] += 1
        elif f < 0:
            out["losers"] += 1
        else:
            out["unchanged"] += 1

    # 거래대금 내림차순 정렬 → 상위 N(top_by_traded) + 대시보드용 전체 행(rows)
    sorted_by_tv = sorted(norm, key=lambda x: x["traded_value"] or 0, reverse=True)

    def _row_card(n: dict[str, Any]) -> dict[str, Any]:
        return {
            "isu_cd": n["isu_cd"],
            "isu_nm": n["isu_nm"],
            "amc": detect_etf_amc(n["isu_nm"]) if kind == "ETF" else None,
            "open": n["open"],
            "close": n["close"],
            "volume": n["volume"],
            "traded_oku": round((n["traded_value"] or 0) / 1e8, 1),
            "market_cap_oku": round((n["market_cap"] or 0) / 1e8, 1) if n["market_cap"] else None,
            "list_shrs": n["list_shrs"],
            "fluc_rt": n["fluc_rt"],
            "base_index_name": n["base_index_name"] or n.get("uly_nm", ""),
        }

    out["top_by_traded"] = [_row_card(n) for n in sorted_by_tv[:top_n]]
    # 대시보드 임베드: ETF/ETN 전수, ELW 만 거래대금 상위 _ELW_DASHBOARD_ROWS 로 cap
    dash_src = sorted_by_tv[:_ELW_DASHBOARD_ROWS] if kind == "ELW" else sorted_by_tv
    out["rows"] = [_row_card(n) for n in dash_src]

    # ETF 운용사별 거래대금 합계 + 종목 수 (top 운용사 10)
    if kind == "ETF":
        amc_agg: dict[str, dict[str, Any]] = {}
        for n in norm:
            amc = detect_etf_amc(n["isu_nm"])
            b = amc_agg.setdefault(amc, {"amc": amc, "count": 0, "traded_value": 0.0})
            b["count"] += 1
            b["traded_value"] += n["traded_value"] or 0
        amc_list = sorted(amc_agg.values(), key=lambda x: x["traded_value"], reverse=True)
        for b in amc_list:
            b["traded_oku"] = round(b["traded_value"] / 1e8, 1)
            del b["traded_value"]
        out["by_amc"] = amc_list[:10]

    return out


# ─── 인사이트 (룰 기반, 결정론) ──────────────────────────────────────


def _fmt_oku(v: float | None) -> str:
    """억원 → 사람이 읽는 문자열. 1만억(=1조) 이상이면 조 단위로."""
    if v is None:
        return "—"
    if abs(v) >= 1e4:
        return f"{v / 1e4:,.1f}조원"
    return f"{v:,.0f}억원"


def compose_insights(overviews: dict[str, Any]) -> list[str]:
    """ETF/ETN/ELW 오버뷰 → 시장 인사이트 5문장 (순수 함수, 외부 호출 없음).

    수치는 모두 ``analyze_etp_market`` 출력(= KRX raw 의 단위 환산값)에서 도출. LLM 미관여.
    데이터가 일부만 있으면 가능한 인사이트만 반환 (graceful). 전부 비면 안내 1문장.
    """
    etf = overviews.get("ETF") or {}
    etn = overviews.get("ETN") or {}
    elw = overviews.get("ELW") or {}
    out: list[str] = []

    etf_total = etf.get("total_traded_oku") or 0.0
    etf_rows = etf.get("rows") or []
    etf_top = etf.get("top_by_traded") or []
    etf_amc = etf.get("by_amc") or []

    # 1) 거래대금 1위 ETF + 점유율
    if etf_top:
        t = etf_top[0]
        share = (t["traded_oku"] / etf_total * 100) if etf_total else None
        share_txt = f" — 전체 ETF 거래대금의 {share:.1f}%" if share is not None else ""
        out.append(f"거래대금 1위 ETF는 {t['isu_nm']} ({_fmt_oku(t['traded_oku'])}){share_txt}.")

    # 2) 운용사 거래대금 1위 + 점유율
    if etf_amc:
        a = etf_amc[0]
        share = (a["traded_oku"] / etf_total * 100) if etf_total else None
        share_txt = f", 점유율 {share:.1f}%" if share is not None else ""
        out.append(
            f"운용사 거래대금 1위는 {a['amc']} ({_fmt_oku(a['traded_oku'])}, {a['count']}종목{share_txt})."
        )

    # 3) 상승/하락 비율 — 강세/약세/혼조
    g, l_ = etf.get("gainers", 0), etf.get("losers", 0)
    if g or l_:
        if g > l_ * 1.2:
            mood = "상승 종목 우위"
        elif l_ > g * 1.2:
            mood = "하락 종목 우위"
        else:
            mood = "혼조"
        out.append(f"ETF 상승 {g}개 / 하락 {l_}개 — {mood}.")

    # 4) 최대 상승 ETF (실제 거래된 종목만)
    traded = [r for r in etf_rows if (r.get("traded_oku") or 0) > 0 and r.get("fluc_rt") is not None]
    if traded:
        best = max(traded, key=lambda r: r["fluc_rt"])
        if best["fluc_rt"] > 0:
            out.append(f"오늘 가장 크게 오른 ETF는 {best['isu_nm']} (+{best['fluc_rt']:.2f}%).")
        else:
            worst = min(traded, key=lambda r: r["fluc_rt"])
            out.append(f"전 종목 약세 — 그나마 낙폭이 작은 ETF는 {best['isu_nm']} ({best['fluc_rt']:+.2f}%), 최대 낙폭은 {worst['isu_nm']} ({worst['fluc_rt']:+.2f}%).")

    # 5) ETP 시장 규모 (3종 합산)
    etp_mc = sum((o.get("total_market_cap_oku") or 0.0) for o in (etf, etn, elw))
    parts = []
    if etf.get("count"):
        parts.append(f"ETF {etf['count']:,}종 {_fmt_oku(etf.get('total_traded_oku'))}")
    if etn.get("count"):
        parts.append(f"ETN {etn['count']:,}종 {_fmt_oku(etn.get('total_traded_oku'))}")
    if elw.get("count"):
        parts.append(f"ELW {elw['count']:,}종 {_fmt_oku(elw.get('total_traded_oku'))}")
    if parts:
        mc_txt = f" · ETP 시총 합계 {_fmt_oku(etp_mc)}" if etp_mc else ""
        out.append(f"시장 규모: {' / '.join(parts)}{mc_txt}.")

    return out or ["시장 데이터가 없습니다."]
