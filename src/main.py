"""오케스트레이션 — fetch → analyze → render → validate.

CLAUDE.md §2: ``main.py`` 만이 모든 모듈을 조립한다.
LLM 슬롯은 룰 기반 fallback 으로 채운다 (Phase 1).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# .env 파일 로드 (이미 환경변수가 있으면 덮어쓰지 않음).
# import 시점에 단 한 번 호출 — main() 내부가 아닌 모듈 최상단에 둬서 다른
# 모듈이 main.py 를 import 할 때도 키가 잡히도록 한다.
load_dotenv()

from src.analyzers import disclosure as disclosure_analyzer
from src.analyzers import financials as financials_analyzer
from src.analyzers import flow as flow_analyzer
from src.analyzers import macro as macro_analyzer
from src.analyzers import market_overview as market_analyzer
from src.analyzers import peer as peer_analyzer
from src.analyzers import price as price_analyzer
from src.cli import CliArgs, parse_args
from src.collectors import dart_openapi, krx_etp, krx_openapi
from src.collectors import macro as macro_collector
from src.config import (
    DISCLAIMER_EN,
    DISCLAIMER_KO,
    DEFAULT_MACRO,
    DISCLOSURE_LOOKBACK_DAYS,
    LLM_DIR,
    MACRO_LOOKBACK_DAYS,
    MARKET_DATE_WALKBACK_DAYS,
    OUTPUT_DIR,
    PEER_N,
    PEER_NORMALIZED_LOOKBACK_DAYS,
    PRICE_LOOKBACK_DAYS,
    RAW_DIR,
    SECTOR_MACRO_MAP,
)
from src.fallbacks import pykrx_price
from src.llm import inject as llm_inject
from src.meta import peers as peers_module
from src.meta import ticker as ticker_module
from src.renderer import charts as chart_builder
from src.renderer import html as html_renderer
from src.scrapers import tp_consensus as tp_module
from src.validators import citations as citations_validator
from src.validators import numbers as numbers_validator

logger = logging.getLogger(__name__)


# ─── 데이터 수집 ─────────────────────────────────────────────────────


def _yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _save_raw(meta_triple: dict[str, Any] | None, raw_dir: Path, ticker: str, name: str) -> None:
    if meta_triple is None:
        return
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{ticker}_{name}.json"
    path.write_text(json.dumps(meta_triple, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_fetch_price(ticker: str, fromdate: str, todate: str) -> dict[str, Any] | None:
    try:
        return pykrx_price.fetch_ohlcv(ticker, fromdate, todate)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s 시세 fetch 실패: %s", ticker, exc)
        return None


def _safe_fetch_flow(ticker: str, fromdate: str, todate: str) -> dict[str, Any] | None:
    """수급 (외/기/개 순매수).

    KRX OpenAPI 카탈로그에 투자자별 매매 API 가 없으므로 pykrx 만 사용.
    pykrx 1.2.x 는 ``KRX_ID``/``KRX_PW`` 환경변수로 data.krx.co.kr 로그인 필요.
    """
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
        logger.info("KRX_ID/KRX_PW 미설정 — 수급 noop")
        return {
            "data": [],
            "source": "noop:investor_flow",
            "tool_args": {"ticker": ticker, "fromdate": fromdate, "todate": todate},
            "fetched_at": _now_iso_utc(),
        }
    try:
        return pykrx_price.fetch_investor_flow(ticker, fromdate, todate)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s 수급 fetch 실패 (pykrx): %s", ticker, exc)
        return None


def _safe_fetch_fundamental(ticker: str, today_yyyymmdd: str) -> dict[str, Any] | None:
    """pykrx 시장 fundamental — KRX_ID/PW 미설정 시 noop."""
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
        return {
            "data": {},
            "source": "noop:fundamental",
            "tool_args": {"ticker": ticker, "date": today_yyyymmdd},
            "fetched_at": _now_iso_utc(),
        }
    try:
        return pykrx_price.fetch_market_fundamental(ticker, today_yyyymmdd)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s fundamental fetch 실패: %s", ticker, exc)
        return None


def _safe_fetch_disclosures(ticker: str, fromdate: str, todate: str) -> dict[str, Any] | None:
    """DART list.json 으로 공시 수집. corp_code 자동 매핑."""
    if not os.environ.get("DART_API_KEY"):
        logger.info("DART_API_KEY 미설정 — 공시 noop")
        return {
            "data": [],
            "source": "noop:disclosure",
            "tool_args": {"ticker": ticker, "fromdate": fromdate, "todate": todate},
            "fetched_at": _now_iso_utc(),
        }

    corp_code = dart_openapi.lookup_corp_code(ticker)
    if not corp_code:
        logger.warning("ticker %s 에 해당하는 corp_code 없음 — 공시 빈결과", ticker)
        return {
            "data": [],
            "source": "dart-openapi:list.json",
            "tool_args": {"ticker": ticker, "corp_code": None, "bgn_de": fromdate, "end_de": todate},
            "fetched_at": _now_iso_utc(),
        }

    try:
        meta = dart_openapi.fetch_disclosure_list(corp_code, fromdate, todate)
        return meta
    except Exception as exc:  # noqa: BLE001
        logger.warning("DART 공시 fetch 실패: %s", exc)
        return None


def _safe_fetch_financials(ticker: str, report_date: date) -> dict[str, Any] | None:
    """재무: 직전 사업보고서(연간) + 가장 최근 분기/반기 보고서를 합쳐 반환."""
    if not os.environ.get("DART_API_KEY"):
        logger.info("DART_API_KEY 미설정 — 재무 noop")
        return {
            "data": [],
            "source": "noop:financials",
            "tool_args": {"ticker": ticker},
            "fetched_at": _now_iso_utc(),
        }

    corp_code = dart_openapi.lookup_corp_code(ticker)
    if not corp_code:
        return {
            "data": [],
            "source": "dart-openapi:fnlttSinglAcntAll.json",
            "tool_args": {"ticker": ticker, "corp_code": None},
            "fetched_at": _now_iso_utc(),
        }

    # 분기 코드: 1Q(11013, ~5월 공시), 반기(11012, ~8월), 3Q(11014, ~11월),
    # 사업보고서(11011, 익년 ~3-4월). 차트용 시계열을 위해 최근 ~4 기간을 시도.
    yr = report_date.year
    candidates: list[tuple[int, int | None]] = [
        (yr - 1, None),  # 직전 사업보고서
        (yr - 2, None),  # 그 전 사업보고서
        (yr - 1, 3),     # 직전 3Q
        (yr - 1, 2),     # 직전 반기
        (yr - 1, 1),     # 직전 1Q
        (yr, 3),
        (yr, 2),
        (yr, 1),
    ]

    rows: list[dict[str, Any]] = []
    success_sources: list[str] = []
    seen_periods: set[str] = set()

    for (year, q) in candidates:
        try:
            if q is None:
                meta = dart_openapi.fetch_financials_annual(corp_code, year)
                period_key = f"{year}-FY"
            else:
                meta = dart_openapi.fetch_financials_quarterly(corp_code, year, q)
                period_key = f"{year}-Q{q}"
            data_rows = meta.get("data") or []
            if not data_rows:
                continue
            if period_key in seen_periods:
                continue
            seen_periods.add(period_key)
            for r in data_rows:
                rr = dict(r)
                rr.setdefault("_period_key", period_key)
                rows.append(rr)
            success_sources.append(meta.get("source", ""))
        except Exception as exc:  # noqa: BLE001
            logger.info("DART 재무 %s/%s 건너뜀: %s", year, q, exc)

    return {
        "data": rows,
        "source": "dart-openapi:fnlttSinglAcntAll.json",
        "tool_args": {
            "ticker": ticker,
            "corp_code": corp_code,
            "periods": sorted(seen_periods),
        },
        "fetched_at": _now_iso_utc(),
    }


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── 데이터 정규화 헬퍼 ──────────────────────────────────────────────


_FLOW_INVESTOR_MAP = {
    # KRX OpenAPI INVST_NM/INVR_NM (한글) → analyzer 컬럼
    "외국인": "외국인",
    "외국인투자자": "외국인",
    "외국인합계": "외국인",
    "기관": "기관",
    "기관계": "기관",
    "기관합계": "기관",
    "개인": "개인",
    "개인투자자": "개인",
}


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        s = str(v).replace(",", "").strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_flow_records(rows: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """수급 raw row → ``[{date, 외국인, 기관, 개인}, ...]`` 형식.

    pykrx 결과는 이미 wide-format (date 인덱스 + 컬럼) 이므로 그대로 통과시킨다.
    KRX OpenAPI 결과는 long-format (basDd, INVST_NM, TRDVAL_NETBY) 이라 pivot 필요.
    """
    if not rows:
        return rows

    # 이미 wide-format 이면 (외국인/기관/개인 컬럼이 있음) 그대로
    sample = rows[0]
    if any(k in sample for k in ("외국인", "기관", "개인", "외국인계", "기관계")):
        return rows

    # KRX OpenAPI: long-format pivot
    by_date: dict[str, dict[str, Any]] = {}
    for r in rows:
        bas = str(r.get("BAS_DD") or r.get("bas_dd") or "").strip()
        if len(bas) == 8 and bas.isdigit():
            d = f"{bas[:4]}-{bas[4:6]}-{bas[6:8]}"
        else:
            d = bas or ""
        invst = str(r.get("INVST_NM") or r.get("INVR_NM") or r.get("invst_nm") or "").strip()
        canonical = _FLOW_INVESTOR_MAP.get(invst)
        if canonical is None:
            continue
        netby = (
            r.get("TRDVAL_NETBY")
            or r.get("NETBY_TRDVAL")
            or r.get("trdval_netby")
            or r.get("NETBY_TRDVOL")
        )
        val = _to_float(netby)
        if val is None:
            continue
        bucket = by_date.setdefault(d, {"date": d})
        bucket[canonical] = val

    return [by_date[k] for k in sorted(by_date.keys())]


# DART account_nm 매핑 (한글) — 다양한 표기를 허용
_DART_ACCOUNT_MAP: dict[str, str] = {
    "매출액": "매출액",
    "수익(매출액)": "매출액",
    "영업수익": "매출액",
    "매출": "매출액",
    "영업이익": "영업이익",
    "영업이익(손실)": "영업이익",
    "당기순이익": "순이익",
    "당기순이익(손실)": "순이익",
    "분기순이익": "순이익",
    "분기순이익(손실)": "순이익",
    "반기순이익": "순이익",
    "반기순이익(손실)": "순이익",
}


def _normalize_financial_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DART fnlttSinglAcntAll row → ``[{period, 매출액, 영업이익, 순이익}, ...]``.

    여러 보고서가 섞여 있으므로 ``_period_key`` 로 group.
    매출은 손익계산서(IS)/포괄손익계산서(CIS) 양쪽에 들어있을 수 있어 첫 매칭 채택.
    """
    if not rows:
        return []

    # period_key → {매출액, 영업이익, 순이익}
    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        period_key = str(r.get("_period_key") or r.get("bsns_year") or "")
        if not period_key:
            continue
        sj_div = str(r.get("sj_div") or "").upper()
        # 재무상태표(BS) 는 스킵 — 손익 항목만
        if sj_div == "BS":
            continue
        account_nm = str(r.get("account_nm") or "").strip()
        canon = _DART_ACCOUNT_MAP.get(account_nm)
        if canon is None:
            continue
        amount = _to_float(r.get("thstrm_amount"))
        if amount is None:
            continue
        bucket = grouped.setdefault(period_key, {"period": period_key})
        # 첫 매칭 우선 (CIS 보다 IS 가 보통 먼저)
        bucket.setdefault(canon, amount)

    # 정렬: 분기는 Q1<Q2<Q3<FY 순; 연도 desc
    def _sort_key(k: str) -> tuple[int, int]:
        # "2025-Q1" → (2025, 1), "2024-FY" → (2024, 4)
        try:
            year_part, suffix = k.split("-", 1)
            year = int(year_part)
        except ValueError:
            return (0, 0)
        if suffix.startswith("Q"):
            try:
                return (year, int(suffix[1:]))
            except ValueError:
                return (year, 0)
        if suffix == "FY":
            return (year, 4)
        return (year, 0)

    return [grouped[k] for k in sorted(grouped.keys(), key=_sort_key)]


# ─── 빌드 ───────────────────────────────────────────────────────────


def build(args: CliArgs) -> Path:
    report_date = args.report_date
    date_str = report_date.isoformat()
    raw_dir = RAW_DIR / date_str
    raw_dir.mkdir(parents=True, exist_ok=True)

    todate = _yyyymmdd(report_date)
    fromdate_price = _yyyymmdd(report_date - timedelta(days=PRICE_LOOKBACK_DAYS))
    fromdate_disc = _yyyymmdd(report_date - timedelta(days=DISCLOSURE_LOOKBACK_DAYS))
    fromdate_macro = _yyyymmdd(report_date - timedelta(days=MACRO_LOOKBACK_DAYS))
    fromdate_peer = _yyyymmdd(report_date - timedelta(days=PEER_NORMALIZED_LOOKBACK_DAYS))

    # 1. ticker 메타
    meta = ticker_module.resolve(args.ticker)
    logger.info("ticker meta: %s", meta)

    # 2. 시세 / 수급 / 공시 / 재무
    price_meta = _safe_fetch_price(args.ticker, fromdate_price, todate)
    _save_raw(price_meta, raw_dir, args.ticker, "price")

    flow_meta = _safe_fetch_flow(args.ticker, fromdate_price, todate)
    _save_raw(flow_meta, raw_dir, args.ticker, "flow")

    disclosure_meta = _safe_fetch_disclosures(args.ticker, fromdate_disc, todate)
    _save_raw(disclosure_meta, raw_dir, args.ticker, "disclosures")

    fin_meta = _safe_fetch_financials(args.ticker, report_date)
    _save_raw(fin_meta, raw_dir, args.ticker, "financials")

    fund_meta = _safe_fetch_fundamental(args.ticker, todate)
    _save_raw(fund_meta, raw_dir, args.ticker, "fundamental")

    # 시총 단일 일자 — 회전율 계산용
    try:
        cap_meta = pykrx_price.fetch_market_cap_single(args.ticker, todate)
        _save_raw(cap_meta, raw_dir, args.ticker, "market_cap")
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s 시총 fetch 실패: %s", args.ticker, exc)
        cap_meta = None

    # TP 컨센서스 — 무료 데이터 소스 모두 robots.txt Disallow: / 정책이라 보류.
    # 유료 API 키 (FnGuide / Refinitiv / Quantiwise 등) 준비 후 BaseTPProvider 구현체
    # 추가 + 아래 라인 활성화. (CLAUDE.md §4 준수)
    tp_meta = None

    # 3. 피어
    peer_note = ""
    if args.peers:
        peer_list = peers_module.validate_override(args.peers, args.ticker)
        peer_note = "사용자 지정 피어"
    else:
        sel = peers_module.auto_select(
            args.ticker,
            meta.sector_code,
            n=PEER_N,
            today_yyyymmdd=todate,
        )
        peer_list = sel.peers
        if sel.degraded and sel.note:
            peer_note = sel.note

    peer_records: dict[str, list[dict[str, Any]]] = {}
    peer_meta_map: dict[str, dict[str, Any]] = {}
    for pt in peer_list:
        m = _safe_fetch_price(pt, fromdate_peer, todate)
        if m is None:
            continue
        _save_raw(m, raw_dir, pt, "price")
        peer_records[pt] = m.get("data", [])
        pm = ticker_module.resolve(pt)
        peer_meta_map[pt] = {"name": pm.name, "ticker": pt}

    # 4. 거시
    macro_series_names = SECTOR_MACRO_MAP.get(meta.sector_name, DEFAULT_MACRO)
    macro_data: dict[str, dict[str, Any]] = {}
    macro_skipped: list[str] = []
    for ms in macro_series_names:
        result = macro_collector.try_fetch_series(ms, fromdate_macro, todate)
        if result is None:
            macro_skipped.append(ms)
            continue
        _save_raw(result, raw_dir, "_macro", ms)
        macro_data[ms] = result

    # ─── Analyze ───────────────────────────────────────────────────
    price_records = (price_meta or {}).get("data", [])
    enriched_price = price_analyzer.enrich(price_records)
    signals = price_analyzer.latest_signals(enriched_price)
    header = price_analyzer.header_summary(enriched_price)

    flow_records = _normalize_flow_records(
        (flow_meta or {}).get("data", []), (flow_meta or {}).get("source", "")
    )
    enriched_flow = flow_analyzer.enrich(flow_records)

    # DART 공시 row 는 ``report_nm`` / ``rcept_dt`` / ``rcept_no`` 그대로
    # disclosure analyzer 가 받을 수 있도록 이미 호환됨 (analyzer §classify 참고).
    disclosure_records = (disclosure_meta or {}).get("data", [])
    classified = disclosure_analyzer.classify(disclosure_records)

    # DART 재무 row 는 account_nm/thstrm_amount 형태 → analyzer 입력 (period/매출액/...) 으로 변환
    fin_records = _normalize_financial_records((fin_meta or {}).get("data", []))
    fin_df = financials_analyzer.normalize(fin_records)

    # Valuation 6 지표 (PER/PBR/EPS/BPS + ROE/부채비율)
    valuation = financials_analyzer.valuation_metrics(
        (fin_meta or {}).get("data", []),
        (fund_meta or {}).get("data", {}),
    )

    # TP 컨센서스 — current_price 기반 upside 계산
    tp_data: dict[str, Any] = dict((tp_meta or {}).get("data", {}) or {})
    cur_price = header.get("price_now")
    if tp_data.get("tp_avg") and cur_price:
        tp_avg_v = float(tp_data["tp_avg"])
        tp_data["upside_pct"] = round((tp_avg_v - float(cur_price)) / float(cur_price) * 100.0, 2)
        tp_data["current_price"] = float(cur_price)

    # §1.6 거래활성도 (회전율, 거래대금 평균 비교)
    market_cap_v = ((cap_meta or {}).get("data", {}) or {}).get("시가총액")
    volume_metrics = price_analyzer.volume_metrics(enriched_price, market_cap_v)

    normalized_peer = peer_analyzer.normalized_frame(
        args.ticker,
        price_records,
        peer_records,
        lookback_days=PEER_NORMALIZED_LOOKBACK_DAYS,
    )

    # 피어 valuation rows
    peer_rows: list[dict[str, Any]] = [
        peer_analyzer.valuation_row(args.ticker, meta.name or args.ticker, price_records)
    ]
    for pt, recs in peer_records.items():
        peer_rows.append(
            peer_analyzer.valuation_row(pt, peer_meta_map[pt]["name"], recs)
        )

    # 거시 카드
    macro_cards: list[dict[str, Any]] = []
    primary_macro_df = None
    primary_macro_name = None
    for name, mt in macro_data.items():
        if name == "USDKRW":
            df = macro_analyzer.normalize_usdkrw(mt.get("data", []))
            value, delta = macro_analyzer.latest_value(df)
            direction = "up" if (delta or 0) > 0 else ("down" if (delta or 0) < 0 else "flat")
            macro_cards.append({"name": "USD/KRW", "value": value, "delta": delta, "direction": direction})
            if primary_macro_df is None:
                primary_macro_df = df
                primary_macro_name = "USD/KRW"

    # ─── Charts ────────────────────────────────────────────────────
    chart_price = chart_builder.price_chart(enriched_price)
    chart_flow = chart_builder.flow_chart(enriched_flow)
    chart_volume = chart_builder.volume_chart(enriched_price)
    chart_flow_share = chart_builder.flow_share_chart(enriched_flow)
    chart_peer = chart_builder.peer_normalized_chart(normalized_peer, args.ticker)
    chart_financials = chart_builder.financials_bars(fin_df)
    chart_macro = ""
    if primary_macro_df is not None:
        chart_macro = chart_builder.macro_chart(primary_macro_name or "macro", primary_macro_df)

    # ─── Slot fallbacks ────────────────────────────────────────────
    s4_macro_text = "거시 시리즈가 없습니다."
    if macro_cards:
        first = macro_cards[0]
        df0 = primary_macro_df if primary_macro_df is not None else None
        if df0 is not None:
            s4_macro_text = macro_analyzer.fallback_s4_macro(first["name"], df0)

    slots = {
        "brief": price_analyzer.fallback_brief(enriched_price, args.ticker),
        "s1_price": price_analyzer.fallback_s1_price(enriched_price),
        "s2_tech": price_analyzer.fallback_s2_tech(signals),
        "s4_peer": peer_analyzer.fallback_s4_peer(args.ticker, normalized_peer),
        "s4_macro": s4_macro_text,
    }

    # Phase 2: LLM 사이드카 inject. 사이드카가 없으면 fallback 그대로.
    sidecar = llm_inject.load_sidecar(args.ticker, date_str, LLM_DIR)
    llm_slots = llm_inject.inject_slots(sidecar)
    if llm_slots:
        slots.update(llm_slots)
        logger.info("LLM 사이드카 적용: %d 슬롯", len(llm_slots))
    llm_slot_keys = set(llm_slots.keys())

    # 섹션별 lens (3 level × 3 timeframe = 9 텍스트/섹션)
    lens = llm_inject.inject_lens(sidecar)
    if lens:
        logger.info("LLM lens 적용: %d 섹션", len(lens))

    # ─── Render context ────────────────────────────────────────────
    sources = []
    if price_meta:
        sources.append(price_meta.get("source", ""))
    if flow_meta:
        sources.append(flow_meta.get("source", ""))
    if disclosure_meta:
        sources.append(disclosure_meta.get("source", ""))
    if fin_meta:
        sources.append(fin_meta.get("source", ""))
    sources_text = " · ".join(s for s in sources if s) or "—"

    ctx: dict[str, Any] = {
        "ticker": args.ticker,
        "name": meta.name or args.ticker,
        "market": meta.market or "—",
        "sector_name": meta.sector_name,
        "as_of": header.get("as_of") or date_str,
        "as_of_compact": (header.get("as_of") or date_str).replace("-", ""),
        "header": header,
        "signals": signals,
        "slots": slots,
        "disclosures": classified,
        "peer_rows": peer_rows,
        "peer_note": peer_note,
        "macro_cards": macro_cards,
        "macro_skipped": macro_skipped,
        "valuation": valuation,
        "tp_consensus": tp_data,
        "volume_metrics": volume_metrics,
        "chart_volume": chart_volume,
        "chart_flow_share": chart_flow_share,
        "chart_price": chart_price,
        "chart_flow": chart_flow,
        "chart_peer": chart_peer,
        "chart_financials": chart_financials,
        "chart_macro": chart_macro,
        "sources_text": sources_text,
        "generated_at": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "disclaimer_ko": DISCLAIMER_KO,
        "disclaimer_en": DISCLAIMER_EN,
        "validation": None,
        "citations": None,
        "llm_slot_keys": llm_slot_keys,
        "lens": lens,
    }

    # ─── analyzer 파생값을 raw_dir 에 함께 저장 (validator multiset 확장) ──
    # raw JSON 만으로는 RSI / 52주 위치 등 derived 값이 unmatched 로 잡히므로,
    # ``{ticker}_enriched.json`` 으로 같이 저장하면 validator 의 ``{ticker}_*.json`` glob
    # 에 자동 인식되어 매칭률이 올라간다.
    # 수급 요약 (5일 누적 / 마지막 일자) — KRW + 억원 양쪽 단위 모두 두어
    # LLM citation 시 어느 단위로 인용해도 매칭되게 한다.
    flow_summary: dict[str, Any] = {}
    if not enriched_flow.empty:
        for canon, candidates in (
            ("foreign", ("외국인합계", "외국인계", "외국인")),
            ("institution", ("기관합계", "기관계", "기관")),
            ("individual", ("개인",)),
        ):
            col = next((c for c in candidates if c in enriched_flow.columns), None)
            if col is None:
                continue
            series = enriched_flow[col].astype(float)
            last5 = float(series.tail(5).sum())
            last_day = float(series.iloc[-1])
            flow_summary[f"{canon}_net_5d_krw"] = last5
            flow_summary[f"{canon}_net_5d_oku"] = round(last5 / 1e8, 1)
            flow_summary[f"{canon}_net_last_day_krw"] = last_day
            flow_summary[f"{canon}_net_last_day_oku"] = round(last_day / 1e8, 1)

    enriched_payload = {
        "price_records": json.loads(enriched_price.to_json(orient="records"))
        if not enriched_price.empty
        else [],
        "signals": signals,
        "header": header,
        "peer_rows": peer_rows,
        "macro_cards": macro_cards,
        "flow_summary": flow_summary,
        "valuation": valuation,
        "tp_consensus": tp_data,
        "volume_metrics": volume_metrics,
    }
    _save_raw(
        {
            "data": enriched_payload,
            "source": "derived:price_analyzer+peer+macro",
            "tool_args": {"ticker": args.ticker},
            "fetched_at": _now_iso_utc(),
        },
        raw_dir,
        args.ticker,
        "enriched",
    )

    out_dir = OUTPUT_DIR / args.ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.html"

    # ticker 메타 캐시 — root_index / ticker_index 가 이름을 표시할 수 있도록
    try:
        (out_dir / "_meta.json").write_text(
            json.dumps(
                {
                    "ticker": args.ticker,
                    "name": meta.name or args.ticker,
                    "market": meta.market or "",
                    "sector_name": meta.sector_name or "",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    # 1차 렌더 (validation 없이)
    html1 = html_renderer.render_skeleton(ctx)
    out_path.write_text(html1, encoding="utf-8")

    # validate (numbers v2 + Phase 2 citations)
    val = numbers_validator.verify_html_against_raw(out_path, raw_dir, ticker=args.ticker)
    numbers_validator.write_sidecar(val, out_path)

    cite_val = citations_validator.verify_html_citations(out_path, raw_dir)
    citations_validator.write_citations_sidecar(cite_val, out_path)

    # 2차 렌더 (validation 포함)
    ctx["validation"] = val
    ctx["citations"] = cite_val
    html2 = html_renderer.render_skeleton(ctx)
    out_path.write_text(html2, encoding="utf-8")

    # index 갱신
    html_renderer.update_ticker_index(args.ticker)
    html_renderer.update_root_index()

    logger.info(
        "DONE %s: checked=%d matched=%d unmatched=%d (%s)",
        out_path,
        val["checked"],
        val["matched"],
        val["unmatched"],
        val["css_class"],
    )
    return out_path


def _last_trading_day(d: date) -> date:
    """주말·한국 공휴일을 건너뛴, ``d`` 이하의 가장 가까운 영업일."""
    try:
        import holidays  # requirements.txt

        kr = holidays.country_holidays("KR")
    except Exception:  # noqa: BLE001
        kr = set()
    cur = d
    while cur.weekday() >= 5 or cur in kr:
        cur -= timedelta(days=1)
    return cur


def _has_trade_data(etp_meta: dict[str, Any]) -> bool:
    """KRX OpenAPI ETP 응답이 실제 매매 데이터를 담고 있는지.

    비영업일을 조회하면 종목 행은 반환되지만 ``TDD_CLSPRC``/``ACC_TRDVAL`` 등 매매
    필드가 모두 빈 문자열이다 (skeleton). 미게시 영업일은 빈 list. 둘 다 False.
    """
    if etp_meta.get("status") != 200:
        return False
    rows = etp_meta.get("data") or []
    return any(
        (r.get("TDD_CLSPRC") or "").strip() or (r.get("ACC_TRDVAL") or "").strip()
        for r in rows
    )


def _resolve_etp_date(report_date: date) -> tuple[date, dict[str, Any]]:
    """KRX OpenAPI ETP 실매매 데이터가 있는 가장 최근 영업일 + 그 날의 ETF 응답.

    당일 데이터가 아직 게시되지 않았으면 (KRX OpenAPI 야간/T+1 게시 지연) 직전
    영업일로 거슬러 올라가며 최대 ``MARKET_DATE_WALKBACK_DAYS`` 영업일 전까지 probe.
    ``KRX_API_KEY`` 미설정이면 즉시 (report_date, 빈 응답) 반환 — 호출부가 pykrx
    fallback 으로 graceful degrade.
    """
    if not os.environ.get("KRX_API_KEY"):
        return report_date, krx_etp.fetch_etf_bydd_trd(_yyyymmdd(report_date))
    day = _last_trading_day(report_date)
    for _ in range(MARKET_DATE_WALKBACK_DAYS + 1):
        etf = krx_etp.fetch_etf_bydd_trd(_yyyymmdd(day))
        if _has_trade_data(etf):
            if day != report_date:
                logger.info(
                    "KRX OpenAPI ETP %s 미게시 → %s 데이터 사용",
                    report_date.isoformat(),
                    day.isoformat(),
                )
            return day, etf
        day = _last_trading_day(day - timedelta(days=1))
    return report_date, krx_etp.fetch_etf_bydd_trd(_yyyymmdd(report_date))


def build_market_overview(args: CliArgs) -> Path:
    """ETF / ETN / ELW 시장 전반 분석 + root index 갱신 + 날짜별 아카이브.

    KRX OpenAPI ``etp/{etf,etn,elw}_bydd_trd`` 가 1순위. 당일 데이터가 아직 게시
    안 됐으면 최근 영업일로 walk-back (``_resolve_etp_date``). ETF 가 끝까지 비면
    pykrx fallback. ETN/ELW 가 비면 graceful — placeholder 메시지.
    아카이브 파일명·시장 기준일(as_of) 은 실제 데이터 날짜를 따른다.
    """
    report_date = args.report_date
    eff_date, krx_etf = _resolve_etp_date(report_date)
    date_str = eff_date.isoformat()
    todate = _yyyymmdd(eff_date)
    raw_dir = RAW_DIR / date_str
    raw_dir.mkdir(parents=True, exist_ok=True)

    overviews: dict[str, Any] = {}
    statuses: dict[str, int] = {}

    # 1) ETF — _resolve_etp_date 가 가져온 응답 재사용. 끝까지 비면 pykrx fallback.
    statuses["etf"] = krx_etf.get("status", 0)
    if krx_etf.get("status") == 200 and krx_etf.get("data"):
        _save_raw(krx_etf, raw_dir, "_market", "etf")
        overviews["ETF"] = market_analyzer.analyze_etp_market(krx_etf["data"], kind="ETF")
    else:
        logger.info("KRX OpenAPI ETF 데이터 없음 (status=%s) → pykrx fallback", krx_etf.get("status"))
        try:
            etf_meta = pykrx_price.fetch_etf_market(todate)
            _save_raw(etf_meta, raw_dir, "_market", "etf")
            overviews["ETF"] = market_analyzer.analyze_etp_market(etf_meta.get("data", []), kind="ETF")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ETF pykrx fallback 실패: %s", exc)
            overviews["ETF"] = market_analyzer.analyze_etp_market([], kind="ETF")

    # 2) ETN — KRX OpenAPI 만 (pykrx 미제공)
    krx_etn = krx_etp.fetch_etn_bydd_trd(todate)
    statuses["etn"] = krx_etn.get("status", 0)
    if krx_etn.get("status") == 200 and krx_etn.get("data"):
        _save_raw(krx_etn, raw_dir, "_market", "etn")
        overviews["ETN"] = market_analyzer.analyze_etp_market(krx_etn["data"], kind="ETN")
    else:
        overviews["ETN"] = market_analyzer.analyze_etp_market([], kind="ETN")

    # 3) ELW — KRX OpenAPI 만
    krx_elw = krx_etp.fetch_elw_bydd_trd(todate)
    statuses["elw"] = krx_elw.get("status", 0)
    if krx_elw.get("status") == 200 and krx_elw.get("data"):
        _save_raw(krx_elw, raw_dir, "_market", "elw")
        overviews["ELW"] = market_analyzer.analyze_etp_market(krx_elw["data"], kind="ELW")
    else:
        overviews["ELW"] = market_analyzer.analyze_etp_market([], kind="ELW")

    insights = market_analyzer.compose_insights(overviews)
    archive_payload = {
        "overviews": overviews,
        "statuses": statuses,
        "as_of": date_str,
        "insights": insights,
    }
    try:
        arch_path = html_renderer.render_market_archive(archive_payload, date_str)
        logger.info("시장 아카이브: %s (인사이트 %d)", arch_path, len(insights))
    except Exception as exc:  # noqa: BLE001
        logger.warning("시장 아카이브 렌더 실패: %s", exc)
    html_renderer.update_root_index(market_overview=archive_payload)
    out_path = OUTPUT_DIR / "index.html"
    logger.info(
        "MARKET DONE %s (기준일 %s): ETF=%d / ETN=%d (status=%s) / ELW=%d (status=%s)",
        out_path,
        date_str,
        overviews.get("ETF", {}).get("count", 0),
        overviews.get("ETN", {}).get("count", 0),
        statuses.get("etn"),
        overviews.get("ELW", {}).get("count", 0),
        statuses.get("elw"),
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.market_only:
        out = build_market_overview(args)
    else:
        out = build(args)
    logger.info("리포트: %s", out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
