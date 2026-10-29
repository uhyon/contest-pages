# AI 공모전·해커톤 카카오톡 알림 에이전트 (LangGraph + Harness)

DACON · DAKER · Dev-Event 에서 AI 공모전·해커톤 공고를 모으고, 규칙으로 검증한 뒤,
**카카오톡으로 핵심 한 줄**을 보내고 **상세 페이지(HTML)** 에서 규칙·일정·상금을 먼저 보여 주는 에이전트입니다.

```
[카카오톡]                                   [상세 페이지]
[이번 주 마감 · D-6]                          ┌ 원문 공고 바로가기 ┐
국부펀드 KIC, AI 에이전트 공모전                 │ 📌 규칙  팀 최대 5인      │ ← 먼저 볼 3가지 (펼침·강조)
한국투자공사 · 공모전 · 대상 일반                │ 🗓 일정  마감 11/12 10:00 │
📌 규칙: 개인/팀 참가 · 팀 최대 5인              │ 💰 상금  총 1,500만원     │
🗓 일정: 마감 11/12(목) 10:00 · …              └──────────────┘
💰 상금: 총 1,500만원                           대회 개요 · 평가 기준 · 데이터 설명 · 동의사항 (접힘)
 [상세 보기]  [원문 공고]
```

## 1. 설치
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

## 2. 실행
| 목적 | 명령 | 필요한 것 |
|---|---|---|
| 키·네트워크 없이 전체 흐름 실습 | `python main.py --offline --today 2026-11-02` | 없음 |
| 하네스 평가 | `python evals/run_evals.py` | 없음 |
| 실제 사이트 수집 + 미리보기 | `python main.py` | 인터넷 (LLM 키는 선택) |
| 실제 카카오톡 발송 | `.env` 에서 `DRY_RUN=0` → 실행 → 승인 질문에 `y` | 카카오 토큰 + `PAGES_BASE_URL` |
| 승인 없이 발송(스케줄용) | `python main.py --auto-send` | 위와 같음 |

결과물
- `outbox/kakao_YYYY-MM-DD.txt` — 카카오톡으로 나갈 메시지 미리보기
- `outbox/pages/YYYY-MM-DD/index.html` — 전체 목록 페이지, 같은 폴더에 공고별 상세 페이지

관심 분야는 `.env` 의 `INTERESTS` 또는 `--interests "AI 개발,데이터 분석,머신러닝"` 으로 바꿉니다.
LLM 키가 없으면 키워드 확장·한 줄 요약을 규칙 기반으로 처리합니다(그래도 전체가 동작).

## 3. 상세 페이지 공개 (휴대폰에서 열리게)
카카오톡 링크는 휴대폰에서 열리므로 `outbox/pages/` 를 웹에 올려야 합니다. 예: GitHub Pages
1. GitHub 에 공개 저장소(예: `contest-pages`)를 만들고 Settings → Pages 를 켭니다.
2. 실행 후 `outbox/pages/` 안의 날짜 폴더를 그 저장소에 올립니다.
3. `.env` 에 `PAGES_BASE_URL=https://<아이디>.github.io/contest-pages` 를 넣습니다.

`PAGES_BASE_URL` 이 비어 있으면 링크가 로컬 파일 주소가 되므로, 실제 발송은 리뷰 단계에서 자동으로 막힙니다.
5장의 자동 실행(GitHub Actions)을 쓰면 이 업로드는 Actions 가 대신합니다(`docs/` 폴더).

## 4. 카카오톡 '나에게 보내기' 설정
1. [Kakao Developers](https://developers.kakao.com) → 내 애플리케이션 → 애플리케이션 추가
2. 앱 키의 **REST API 키**를 `.env` 의 `KAKAO_REST_API_KEY` 에 넣습니다.
3. 카카오 로그인 → 활성화 ON, Redirect URI 에 `http://localhost:8080/callback` 등록
4. 동의항목 → **카카오톡 메시지 전송(talk_message)** 을 선택 동의로 설정
5. **[앱] → [제품 링크 관리] → [웹 도메인]** → [도메인 등록]에서 링크로 쓰일 도메인 등록 (최대 10개, 경로 없이 도메인만):
   `PAGES_BASE_URL` 의 도메인(예: `https://uhyon.github.io`), `https://dacon.io`, `https://daker.ai`
   (등록하지 않은 도메인 링크는 카카오톡에서 열리지 않습니다. Dev-Event 공고의 원문은 사이트가 제각각이라,
   그런 경우에는 상세 페이지의 "원문 공고 바로가기" 버튼을 쓰세요.)
6. 토큰 발급(최초 1회): `python scripts/kakao_login.py` → 안내대로 로그인·동의 후 주소 붙여 넣기
   → `data/.kakao_token.json` 에 저장되고, 이후 실행마다 자동으로 갱신됩니다.

## 5. 자동 실행 (GitHub Actions, 월·목 오전 9시)
이 폴더 전체가 GitHub 저장소 `contest-pages` 입니다. 코드와 상세 페이지(`docs/`)가 함께 들어 있고,
`.github/workflows/contest-alert.yml` 이 매주 월·목 09:00(KST)에 실행됩니다.

실행할 때마다
1. 사이트 수집 → 검증 → 상세·목록 페이지를 `docs/YYYY-MM-DD/` 에 생성
2. 페이지를 저장소에 올리고 GitHub Pages 에 반영될 때까지 대기
3. **아직 보낸 적 없는 새 공고만** 카카오톡으로 발송 (없으면 "새 공고 없음" 안내 1통)
4. 보낸 공고를 `data/sent.json` 에 기록해 저장소에 저장 → 다음 실행에서 제외

### 처음 한 번 설정
1. **Pages 위치 변경**: 저장소 Settings → Pages → Branch 를 `main` / **`/docs`** 로 바꾸고 Save
2. **Secrets 등록**: Settings → Secrets and variables → Actions → **Secrets** 탭 → New repository secret
   | 이름 | 값 |
   |---|---|
   | `KAKAO_REST_API_KEY` | `.env` 의 같은 값 |
   | `KAKAO_CLIENT_SECRET` | `.env` 의 같은 값 |
   | `KAKAO_REFRESH_TOKEN` | `data/.kakao_token.json` 의 `refresh_token` 값 |
   | `GH_PAT` (권장) | 카카오 리프레시 토큰이 바뀌면 위 Secret 을 자동 갱신하는 데 쓰는 토큰 (아래 참고) |
   | `GOOGLE_API_KEY` (선택) | LLM 을 쓸 때만 |
3. **Variables 등록**: 같은 화면 → **Variables** 탭 → `PAGES_BASE_URL` = `https://uhyon.github.io/contest-pages`
4. **시험 실행**: Actions 탭 → contest-alert → Run workflow

`GH_PAT` 만들기: GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token →
Repository access 는 `contest-pages` 만, Permissions → Repository → **Secrets: Read and write** → 생성된 값을 `GH_PAT` 에 등록.
없으면 약 두 달 뒤 카카오 토큰이 만료돼 실행이 실패하고(GitHub 이 메일로 알려 줌), 그때 `python scripts/kakao_login.py` 로
다시 발급해 `KAKAO_REFRESH_TOKEN` 을 손으로 바꿔 주면 됩니다.

참고: GitHub 예약 실행은 몇십 분 늦게 시작될 수 있습니다. 보낸 기록을 초기화하려면 `data/sent.json` 을 지우세요.

## 6. 구조
```
.github/       contest-alert.yml (월·목 09:00 자동 실행)
AGENTS.md      상시 규칙 (무엇을, 어떤 규칙으로)
docs/          GitHub Pages 로 공개되는 상세·목록 페이지 (Actions 가 생성)
PLAN.md        단계·리스크·검증 방법
checklist.md   작업 후 체크
skills/        반복 절차 (source-intake, qa-deadline-links, kakao-release)
evals/         기대 결과 샘플 + 자동 평가 + 하네스 OFF 기준선
scripts/       kakao_login.py (카카오 토큰 최초 발급)
data/fixtures/ offline 용 가상 데이터 (각 사이트 실제 응답 형식)
agent/
  state.py     State 스키마
  rules.py     코드 규칙(날짜·필수값·마감·중복·한 줄 요약·근거 검사·발송 전 리뷰)
  tools.py     외부 연동(사이트 HTTP·LLM·카카오·파일) — offline/dry-run 자동 전환
  sources/     사이트별 파서 (dacon, daker, dev_event, __NUXT__ 파서, HTML 정리)
  render.py    상세 페이지·목록 페이지·카카오 템플릿 조립
  nodes.py     노드 함수
  graph.py     그래프 조립 (조건부 엣지 2개, send 직전 interrupt)
main.py        실행 진입점
```

그래프: `plan_filters → collect → filter → validate ⇄ broaden_filters → fetch_details → summarize → build_pages → select_new → compose_kakao → review → (승인) publish → send | abort`

## 7. 데이터 갱신
- 수집 사이트를 추가할 때는 `skills/source-intake/SKILL.md` 절차를 따르고 `agent/sources/` 에 파서, `agent/tools.py` 에 가져오기만 추가합니다.
- 사이트 구조가 바뀌면 해당 파서만 고치면 됩니다. 수집 실패한 사이트는 로그에 남기고 나머지로 계속 진행합니다.
- 규칙을 바꾸면 `python evals/run_evals.py` 로 다시 확인합니다.

※ `data/fixtures` 는 실습용 가상 데이터입니다. 실제 공고가 아닙니다.
