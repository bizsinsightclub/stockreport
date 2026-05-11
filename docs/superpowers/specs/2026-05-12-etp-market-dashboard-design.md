# ETP 시장 인터랙티브 대시보드 + 인사이트 — 설계

작성일: 2026-05-12
상태: 승인됨 (사용자 확인 완료, 구현 진행)

## 문제

`data/output/market/{date}.html` 와 루트 `index.html` 의 시장 섹션이 "ETF 거래대금 상위 30"
등 평평한 정적 테이블 나열뿐이다. 운용사별/거래대금순/거래량순 등으로 쉽게 보기 어렵고,
데이터에 기반한 요약 인사이트가 없다.

## 목표

1. `market/{date}.html` 을 클라이언트 사이드(vanilla JS) 인터랙티브 대시보드로 — 정렬(컬럼
   클릭 + 드롭다운), 필터(운용사/기초자산 드롭다운), 검색(종목명), ETF/ETN/ELW 탭 전환.
2. 페이지 최상단에 데이터 기반 인사이트 5개 (룰 기반 결정론 계산, LLM 아님).
3. 정적 HTML 유지 — 새 Python 의존성 0, JS 라이브러리 0. GitHub Pages 그대로 동작.

## 제약 (CLAUDE.md)

- 정적 HTML + 서버 없음 (Streamlit/Dash 금지). 클라이언트 JS는 OK.
- 새 의존성 금지. Plotly는 차트용이며 여기선 불필요(테이블).
- 디자인 토큰 그대로 (`--accent` 골드, `--up`/`--down` 한국 관습 색, JetBrains Mono 숫자,
  Fraunces/Noto Sans KR). 새 폰트 금지.
- 환각 방지: 인사이트·테이블 수치는 모두 KRX OpenAPI raw 에서 단위 환산만 거친 값. LLM
  미관여. (시장 페이지는 원래 numbers validator 대상 아님 — 순수 KRX 데이터.)

## 구현 방식

**A. 데이터 임베드 + JS 렌더** (택일). `<script type="application/json" id="etp-data">` 에
ETP_DATA(`{etf:[...], etn:[...], elw:[...]}`) 임베드 → vanilla JS가 `<tbody>` 렌더·정렬·필터.
- HTML에 데이터 1회만 (≈200–300KB, gzip 후 작음).
- `<script>` 는 numbers validator가 자동 제외 → false positive 없음.
- no-JS: `<noscript>` 안내 + 정적 거래대금 상위 10 fallback 테이블 (`data-noverify="true"`).

(대안 B = 서버사이드 전체 테이블 + DOM 정렬/숨김 → DOM에 ~1800 `<tr>`, 모든 행 data-noverify
필요, 더 무거움. 기각.)

## 데이터 흐름

- `src/analyzers/market_overview.py`
  - `analyze_etp_market(rows, *, kind, top_n=30)` 출력에 **`rows`** 추가: 정규화된 전체 행
    (`isu_cd, isu_nm, amc(ETF)/uly_nm(ETN·ELW), close, fluc_rt, volume, traded_oku,
    market_cap_oku, list_shrs, base_index_name`). ETF/ETN 전수, **ELW는 거래대금 상위 300** 으로
    cap. 기존 `top_by_traded`(30), `by_amc`(10), `count`, `total_*_oku`, `gainers/losers` 등은
    요약·no-JS용으로 유지.
  - 새 함수 `compose_insights(overviews: dict[str, Any]) -> list[str]` — ETF/ETN/ELW 오버뷰에서
    인사이트 5문장(순수 함수, 외부 호출 없음). 데이터가 비면 가능한 것만 (graceful).
- `src/main.py` `build_market_overview`
  - `overviews[kind]` 가 `rows` 를 포함하게 됨 (analyze 함수 변경으로 자동).
  - `insights = market_analyzer.compose_insights(overviews)` 호출.
  - `archive_payload = {"overviews": overviews, "statuses": statuses, "as_of": date_str, "insights": insights}`.
  - `render_market_archive(archive_payload, date_str)` → 새 템플릿 사용.
  - `update_root_index(market_overview=archive_payload)` → 루트도 `insights` 사용.

## 인사이트 5개 (`compose_insights`, 모두 ETF 기준 + 마지막은 3종 합산)

1. **거래대금 1위 ETF + 점유율** — "거래대금 1위는 {isu_nm} ({traded_oku}억원) — 전체 ETF 거래대금의 {pct}%"
2. **운용사 거래대금 1위 + 점유율** — "운용사별로는 {amc}이(가) 거래대금 {oku}억원({count}종목, 점유율 {pct}%)으로 선두"
3. **상승/하락 비율** — "ETF 상승 {gainers}개 / 하락 {losers}개 — 시장 [강세 우위 / 약세 우위 / 혼조]"
4. **최대 상승 ETF** — "오늘 가장 크게 오른 ETF는 {isu_nm} (+{fluc_rt}%)" (거래대금>0 인 것만)
5. **시장 규모** — "ETF {n}종 거래대금 {f}억 / ETN {n}종 {h}억 / ELW {n}종 {i}억 — ETP 시총 합계 {j}조원"

(필요시 #5 대신 "거래대금 상위 5 ETF 집중도 {pct}%" 로 교체 가능 — 구현 시 #5 채택, 토글 변수로 쉽게 교체 가능하게.)

## 템플릿

- 새 파일 `src/renderer/templates/market_dashboard.html.j2` — 아카이브 전용. `render_market_archive`
  가 이걸 렌더 (현재는 `root_index.html.j2` 를 `archive_mode=True` 로 씀 → 변경).
  - 헤더: "KRX 시장 개요 · {as_of}" + "← 메인으로" 링크.
  - 요약 카드 3개 (ETF/ETN/ELW 종목수·거래대금 합계).
  - **인사이트 섹션**: `insights` 5문장을 카드/리스트로.
  - **탭 위젯**: `[ETF] [ETN] [ELW]` 버튼 → 활성 탭의 컨트롤+테이블 표시.
    - 컨트롤: 정렬 드롭다운(거래대금/거래량/등락률/시총) · 필터 드롭다운(ETF=운용사, ETN·ELW=기초자산)
      · 검색 input(종목명 substring).
    - 테이블: `<thead>` 컬럼 클릭 시 정렬(asc/desc 토글). `<tbody>` 는 JS가 채움.
    - 헤더 컬럼: ETF = 운용사 / 종목명(코드) / 종가 / 등락 / 거래량 / 거래대금(억)↓ / 시총(억) / 기초지수.
      ETN·ELW = 종목명(코드) / 종가 / 등락 / 거래량 / 거래대금(억)↓ / 시총(억) / 기초자산.
  - `<noscript>`: "JS가 꺼져 있어 인터랙티브 표가 안 보입니다 — 거래대금 상위 10만 표시" + 정적 mini 테이블 3개(`data-noverify="true"`).
  - 임베드: `<script type="application/json" id="etp-data">{...}</script>` + `<script> ... </script>` (vanilla JS ≈80–120줄).
  - 푸터: 기존 `root_index` 푸터와 동일 (데이터 소스, generated_at, 디스클레이머).
- `src/renderer/templates/_etp_styles.html.j2` (신규 파셜) — 디자인 토큰 + 공통 레이아웃 CSS.
  `root_index.html.j2` 와 `market_dashboard.html.j2` 양쪽에서 `{% include %}`. (중복 방지 — CLAUDE.md
  §6/§11 "디자인 토큰 일관성" 준수.) 대시보드 전용 CSS(.tabs, .controls, sortable th 등)는
  `market_dashboard.html.j2` 안에 둠.
- `src/renderer/templates/root_index.html.j2` — 시장 섹션 슬림화:
  - 유지: 요약 카드 3개.
  - **추가**: 인사이트 5줄 (작은 리스트), "전체 시장 대시보드 →" 링크 (최신 `market/{date}.html`).
  - **제거**: "ETF 운용사 거래대금 상위" amc-grid, "ETF 거래대금 상위 30" 테이블, ETN 테이블, ELW 테이블
    (모두 대시보드 페이지로 이동).
  - 유지: "분석된 종목" 리스트, "지난 시장 리포트" 아카이브 목록 (`07 / ARCHIVE`).
  - `<style>` 은 `{% include "_etp_styles.html.j2" %}` 로 교체 (기존 인라인 토큰 블록 제거).

## renderer/html.py

- `render_market_archive(market_overview, date_str)` — `get_template("market_dashboard.html.j2")` 로 변경.
  `archive_mode` 인자는 더 이상 불필요(별도 템플릿). `market_overview` dict에 `insights`, 각 kind의 `rows` 포함.
- `update_root_index(...)` — 변경 없음 (이미 `market_overview` dict 통째로 템플릿에 넘김 → 템플릿이
  `market_overview.insights` 사용). `_list_market_archives` 그대로.

## JS 사양 (`market_dashboard.html.j2` 내부)

- `const DATA = JSON.parse(document.getElementById('etp-data').textContent)` — `{etf, etn, elw}`.
- 상태: `cur = {kind:'etf', sortKey:'traded_oku', sortDir:-1, amc:'', q:''}`.
- `render()`: `DATA[cur.kind]` 복사 → amc/uly 필터 → q substring 필터(isu_nm) → sortKey/sortDir 정렬 →
  `<tbody>` innerHTML 생성. 등락 양/음에 `.up`/`.down` 클래스. 숫자는 천단위 콤마(`toLocaleString('ko-KR')`).
- 탭 버튼 클릭: `cur.kind` 변경, sortKey 기본값 reset, 필터 드롭다운 옵션 재구성(ETF=운용사 set, 그 외=uly set), `render()`.
- `<th data-key="...">` 클릭: 같은 key면 `sortDir *= -1`, 아니면 key 변경 + dir=-1(거래대금/거래량/시총은 내림차순 시작, 종목명은 오름차순). `render()`.
- 정렬 드롭다운 change → sortKey 변경 + dir 기본. 검색 input → `cur.q`, debounce 불필요(데이터 작음). 필터 드롭다운 change → `cur.amc`.
- 접근성: 탭은 `<button>`, 키보드 동작 자동. 컬럼 정렬 표시는 `↑/↓` 아이콘.

## 안 건드리는 것

종목 리포트(`{ticker}/{date}.html`, `dashboard.html.j2`), `validators/`, ETP 날짜 walk-back, 빌드 파이프라인,
ticker_index. `market/{date}.html` 은 numbers validator 미대상(기존과 동일).

## 검증

- `py -3.11 -m src.main --market --date 2026-05-12` → walk-back으로 기준일 2026-05-08 →
  `market/2026-05-08.html` 가 인사이트 5 + ETF/ETN/ELW 탭·정렬·필터 동작. 루트 `index.html` 은 요약+인사이트+링크.
- playwright로 로컬 HTTP 서버 띄워 탭 전환·정렬·필터·검색 스모크 확인 + 스크린샷.
- `python -c "import ast; ..."` 문법 체크. (test_render.py 는 선행 실패 상태 — 이번 변경 무관.)

## 파일 변경 요약

- 신규: `src/renderer/templates/market_dashboard.html.j2`, `src/renderer/templates/_etp_styles.html.j2`,
  `docs/superpowers/specs/2026-05-12-etp-market-dashboard-design.md` (본 문서)
- 수정: `src/analyzers/market_overview.py` (rows 추가 + compose_insights), `src/main.py` (insights 호출),
  `src/renderer/html.py` (render_market_archive 템플릿 교체), `src/renderer/templates/root_index.html.j2`
  (시장 섹션 슬림화 + 인사이트 + include), `CLAUDE.md §2` (템플릿 목록), `README` (필요시)
- 산출물: `data/output/market/{date}.html`, `data/output/index.html` 재생성
