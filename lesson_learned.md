# Lessons Learned — KRX Reporter

> 작업하다 부딪힌 함정·결정의 근거를 모아둔 파일. 새 세션에서 `progress.md` 와 함께 읽으면 같은 실수 반복 안 함.

---

## 2026-05-11 / 12 세션

### L1. `git stash -u` + 워킹트리 변경 명령 + 조용한 `git stash pop` 실패 = 편집 유실 ⚠️
- **무슨 일**: 미커밋 src 편집이 있는 상태에서 "`test_render.py` 가 HEAD 에서도 실패하나" 확인하려고 `git stash -u >/dev/null 2>&1; py -3.11 test_render.py; git stash pop >/dev/null 2>&1` 를 한 줄로 실행. `test_render.py` 가 `data/output/329180/2026-05-11.html` 와 `data/output/index.html` 를 더미 데이터로 덮어씀 → `git stash pop` 시 그 파일들이 stash 와 충돌 → pop 실패 → `>/dev/null 2>&1` 가 실패 메시지를 숨김 → "`(restored)`" 만 출력되어 성공한 줄 알았으나 **src 편집은 여전히 stash 에 갇혀 있었음**. 다음 빌드들이 옛 코드로 돌아감.
- **복구**: `git checkout HEAD -- data/output/...` (실제 리포트 복원) → `rm -rf data/output/market/` (stale) → `git stash pop` (충돌 없이 적용) → 다시 `git checkout HEAD -- data/output/...` (stash 안 더미 파일 또 복원됨) → 재빌드.
- **교훈**:
  1. `git stash` 한 뒤에는 워킹트리를 건드리는 어떤 명령도 돌리지 말 것 (특히 빌드/테스트).
  2. `git stash pop` 출력을 절대 `>/dev/null 2>&1` 로 숨기지 말 것. 조용히 실패한다.
  3. "HEAD 에서 재현되나" 확인은 `git stash` 대신 별도 worktree (`git worktree add`) 나 임시 clone 으로.

### L2. `test_render.py` 는 위험한 스크립트다
- `TICKER = "329180"` 하드코딩 → `data/output/329180/{today}.html` 를 5행짜리 미니 fixture 더미로 덮어씀. `update_ticker_index` / `update_root_index` 도 호출 → `data/output/329180/index.html`, `data/output/index.html` 까지 덮어씀.
- 게다가 lens 커밋 이후로는 `assert 'data-llm-slot="brief"' in body` 가 **항상 실패** — dashboard.html.j2 가 `{% if 'brief' in llm_slot_keys %}` 게이트를 추가했는데 `test_render.py` 의 ctx 는 `llm_slot_keys`/`slots` 를 안 넘김. (이번 변경과 무관한 선행 버그)
- **교훈**: `test_render.py` 는 함부로 돌리지 말 것. 돌렸으면 `git checkout HEAD -- data/output/` 로 복구. 언젠가 (a) ctx 에 `llm_slot_keys`/`slots`/`lens`/`citations` 추가해 assertion 통과시키고 (b) 출력 디렉토리를 임시 dir 로 빼는 게 맞음.

### L3. KRX OpenAPI ETP 는 T+1 게시 + 비영업일 skeleton 행
- `etp/{etf,etn,elw}_bydd_trd?basDd=오늘` → status 200 인데 `OutBlock_1: []` (당일분 미게시, 보통 다음날 채워짐).
- `basDd=일요일` 같은 비영업일 → 종목 행 1099개 다 오는데 `TDD_CLSPRC`, `ACC_TRDVAL`, `FLUC_RT` 등 매매 필드가 **빈 문자열** (skeleton). `LIST_SHRS` 정도만 값 있음.
- 그래서 "행 개수만" 보고 데이터 유무 판단하면 안 됨. → `_resolve_etp_date()` 가 `holidays` 패키지로 주말·공휴일 스킵하고, `_has_trade_data()` 가 `TDD_CLSPRC`/`ACC_TRDVAL` 비어있으면 skip → 최대 7 영업일 전까지 walk-back.
- 결과: 시장 페이지 "시장 기준일" 이 빌드일보다 며칠 전일 수 있음 — 정상. hourly 빌드가 매시간 돌면서 KRX 가 게시하는 순간 새 날짜 페이지가 생김.

### L4. 정적 HTML 에서 "인터랙티브"는 클라이언트 vanilla JS 로 충분
- CLAUDE.md 가 Streamlit/Dash 를 금지하지만, **정렬·필터·검색은 브라우저 JS 로 다 됨** — GitHub Pages 그대로 서빙. 새 의존성 0.
- 패턴: 데이터를 `<script type="application/json" id="...">{{ data | tojson }}</script>` 로 임베드 → JS 가 `JSON.parse` 후 `<tbody>` 재렌더. Jinja `tojson` 은 `<`,`>`,`&` 를 `<` 등으로 이스케이프해서 `</script>` 깨짐 없음.
- `validators/numbers.py` 는 `<script>` 서브트리를 자동 제외하므로 임베드 데이터가 false positive 안 만듦. (애초에 시장 페이지는 numbers validator 대상도 아님 — `build_market_overview` 는 안 거침.)
- ETF/ETN 전수(~1100/~400), ELW 만 거래대금 상위 300 으로 cap. HTML ~600KB (gzip 후 작음, 종목 리포트 HTML 도 비슷한 크기).

### L5. GitHub Pages 배포 지연
- `git push` 후 Pages 가 새 빌드를 서빙하기까지 1~5분 (가끔 더). 그 사이 옛 버전이 보임.
- `raw.githubusercontent.com/{owner}/{repo}/main/{path}` 는 push 즉시 갱신 → 레포 반영 여부 확인은 이걸로. (Pages 캐시는 `?cb=1` 같은 쿼리 파라미터로도 안 뚫림.)
- 로컬 파일(`data/output/...`)을 브라우저로 직접 열면 즉시 정상.

### L6. LLM 코멘트 자동화는 "로컬 실행"이어야 한다
- `/schedule` (Claude Code routine) 은 클라우드 원격 에이전트 → 한국 IP(pykrx 필수), 로컬 `.env`(KRX_ID/PW, DART_KEY), 로컬 `data/raw/`(gitignore — push 안 됨) 에 접근 불가 → 이 프로젝트엔 부적합.
- `/loop` 은 세션을 계속 띄워둬야 함 → "매일 정해진 시간"엔 부적합.
- 정답: **Windows 작업 스케줄러 → `claude` 헤드리스** (`claude -p "/report-stock <ticker>" --dangerously-skip-permissions`). 로컬에서 빌드·사이드카 작성·재빌드·검증·커밋/푸시. 헤드리스라 권한 프롬프트 못 띄우니 `.claude/settings.json` allowlist 또는 `--dangerously-skip-permissions` 필요.

### L7. 빌드는 background + Monitor/until-loop 으로 기다리기
- `py -3.11 -m src.main <ticker>` 는 KRX 로그인 + MCP 초기화로 ~2.5분. `run_in_background: true` 로 띄우고, `until grep -q "DONE\|Traceback" <output>; do sleep 5; done` 로 대기. 포그라운드 `sleep 45` 같은 건 차단됨.

---

## 영속 원칙 (CLAUDE.md 요약 — 잊지 말 것)

- 환각 0 이 존재 이유. LLM 출력의 **모든 numeric claim** 은 `<span data-cite="file:json-path:value">` wrap, `validators/citations.py` 가 raw 출처 매칭 검증 (mismatch >5% 면 배지 fail).
- LLM SDK 자동 호출 금지 — LLM 코멘트는 Claude Code 세션이 직접 `data/llm/{ticker}/{date}.json` 사이드카로 작성, `src/llm/inject.py` 가 빌드 시 슬롯에 inject. 새 SDK 의존성 추가 불필요.
- 재현성 > 성능. 매 빌드 raw JSON 스냅샷을 `data/raw/{date}/` 에 메타 트리플(`{data, source, tool_args, fetched_at}`) 형식으로 보존.
- 모듈 의존성: `analyzers/` 는 순수 함수(외부 호출 import 금지), `renderer/` 는 raw 직접 안 만짐, `validators/` 는 어떤 src 모듈도 import 안 함, `main.py` 만 조립.
- 차트는 Plotly 서버사이드 렌더 → 정적 HTML embed. 디자인 토큰(`--accent` 골드, `--up` 빨강/`--down` 파랑 한국 관습, JetBrains Mono 숫자, Fraunces/Noto Sans KR) 고정 — 새 폰트·라이브러리 금지.
