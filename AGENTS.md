# AGENTS.md

## Project
대한민국에서 열리는 AI 관련 공모전·해커톤·경진대회 공고를 정해 둔 사이트에서 수집해
정규화·검증한 뒤, 카카오톡(나에게 보내기)으로 핵심만 알려 주고
링크로 상세 페이지(HTML)를 열어 보게 하는 LangGraph 에이전트를 만든다.

## Sources (초기 버전)
- DACON (dacon.io) — 목록·상세가 페이지 안의 `__NUXT__` 데이터에 있다.
- DAKER (daker.ai) — DACON 에서 해커톤을 누르면 열리는 원문 사이트. 공개 JSON API.
- Dev-Event (github.com/brave-people/Dev-Event) — README 마크다운. `대회` 태그만 공모전으로 본다.
- AI 커넥트(aiconnect.kr)는 2026-07-31 서비스 종료로 제외했다.

## Product goal
사용자가 여러 사이트를 따로 뒤지지 않아도
- 관심 분야(AI 개발·데이터 분석·머신러닝) 공고를 카카오톡으로 짧게 받아 보고
- 공고마다 **규칙/가이드라인 · 상세 일정 · 상금 및 혜택** 3가지를 가장 먼저 확인하고
- 상세 페이지에서 나머지(대회 개요·평가 기준·데이터 설명·동의사항)를 필요할 때 펼쳐 보고
- 카카오톡과 상세 페이지 어디서든 원문 공고로 바로 이동할 수 있어야 한다.

## Primary user scenarios
1. 사용자가 관심 분야 공고를 카카오톡으로 받는다.
2. 카카오톡에서 규칙·일정·상금 한 줄 요약만 보고 관심 있는 공고를 고른다.
3. "상세 보기"로 3항목이 맨 위에 강조된 상세 페이지를 연다.
4. "원문 공고"로 신청 페이지에 바로 간다.

## Non-negotiable product rules
- 카카오톡 공고 메시지에는 title, provider, target, D-day, 규칙·일정·상금 한 줄, 상세 페이지 링크, 원문 링크를 반드시 넣는다.
- 카카오톡 본문은 200자 이하로 한다. 공고 수는 MAX_KAKAO_ITEMS 까지 보내고 나머지는 다음 알림으로 미룬다.
- 카카오톡에는 **새 공고만** 보낸다. 이미 보낸 공고(data/sent.json, 원문 url 기준)는 빼되, 상세·목록 페이지에는 접수 중인 공고를 모두 남긴다.
- 새 공고가 0건이면 "지난 알림 이후 새 공고가 없습니다" 안내 1통만 보낸다.
- 상세 페이지는 규칙/가이드라인 → 상세 일정 → 상금 및 혜택을 맨 앞에 펼쳐서 강조하고,
  대회 개요·평가 기준·데이터 설명·동의사항은 그 뒤에 접어 둔다. 맨 위와 맨 아래에 원문 링크를 둔다.
- 원문에 해당 섹션이 없으면 "정보 없음"으로 표시한다(지어내지 않는다).
- 마감된 공고(end_date < today)는 넣지 않는다.
- 중복 공고는 제거한다.
- 오늘 마감 / 이번 주 마감(D-7 이내) 뱃지를 붙이고, 마감 임박 순으로 정렬한다.
- 수집 결과에 없는 공고·링크·날짜·금액을 만들어 내지 않는다(LLM 추측 금지).
- 유효한 공고가 0건이면 "이번에는 조건에 맞는 공고가 없습니다" 안내 메시지를 보낸다.
- 실제 발송은 사람의 승인(또는 --auto-send 플래그)이 있을 때만 한다. 기본값은 DRY_RUN.
- 정기 실행은 GitHub Actions(.github/workflows/contest-alert.yml)로 매주 월·목 09:00 KST 에 한다.
- 카카오톡을 보내기 전에 상세 페이지를 먼저 공개(push)하고 GitHub Pages 반영을 기다린다.

## Tech rules
- LangGraph StateGraph 로 구현하고, 노드 하나는 한 가지 일만 한다.
- 판단(필터 키워드 생성·확장, 섹션 → 핵심 한 줄 요약)은 LLM 노드가,
  규칙(날짜 정규화, 필수값·마감·중복 검사, HTML·카카오 템플릿 조립, 발송)은 코드 노드가 맡는다.
- 링크·날짜·기관명·섹션 본문은 LLM이 쓰지 않고 검증된 데이터에서 코드로 조립한다.
- LLM 한 줄 요약은 숫자가 원문에 모두 있어야 채택한다(rules.grounded). 아니면 규칙 기반 값으로 바꾼다.
- 순환(재필터)은 MAX_ATTEMPTS 로 제한하고, invoke 시 recursion_limit 을 반드시 건다.
- API 키·토큰은 .env / data/.kakao_token.json 으로만 읽고 코드·로그·메시지·페이지에 출력하지 않는다.
- 외부 키·네트워크가 없어도 offline 모드(fixture)로 전체 그래프가 돌아가야 한다.
- 검증 규칙은 agent/rules.py, 외부 연동(HTTP·LLM·카카오)은 agent/tools.py,
  사이트별 파싱은 agent/sources/, 출력물 조립은 agent/render.py 에 둔다.

## Commands
- install: pip install -r requirements.txt
- run (offline): python main.py --offline --today 2026-11-02
- run (real sites, dry-run): python main.py
- kakao token (최초 1회): python scripts/kakao_login.py
- send for real: DRY_RUN=0 + 승인 질문에 y, 또는 python main.py --auto-send
- scheduled: GitHub Actions contest-alert (월·목 09:00 KST), 수동 실행은 Actions 탭 → Run workflow
- eval: python evals/run_evals.py

## Data quality rules
- 날짜는 YYYY-MM-DD 형식으로 정규화한다. 실패하면 raw_date 에 원문을 보존하고 invalid 로 처리한다.
- 연도가 없는 Dev-Event 날짜는 해당 월 섹션 제목(`26년 11월`)의 연도를 쓴다.
- DAKER 시각(UTC)은 KST 로 바꿔 표시한다.
- provider + title + end_date 조합(공백·대소문자 무시)이 같거나, 원문 url 이 같으면 중복으로 본다.
  (먼저 수집한 DACON·DAKER 쪽을 남긴다)
- url, provider, title, end_date 중 하나라도 비면 invalid 로 처리한다.
- url 은 http(s) 로 시작하는 절대경로여야 한다.
- end_date 가 오늘보다 이전이면 expired=true 로 표시하고 제외한다.
- invalid / expired / duplicate 는 버리지 말고 rejected 목록에 reason 과 함께 남긴다.
- 원문 섹션 HTML 은 허용 태그만 남기고 script·style·data:·javascript: 를 제거한다.

## Review expectations
- 실행이 끝나면 valid N건, rejected M건(사유별)을 로그로 출력한다.
- 발송 전에 PAGES_DIR/YYYY-MM-DD/ (로컬 outbox/pages, Actions docs) 에 상세·목록 페이지를, outbox/kakao_YYYY-MM-DD.txt 에 카카오 미리보기를 저장한다.
- 실제 발송 시 PAGES_BASE_URL 이 없거나 http(s) 주소가 아니면 리뷰에서 막는다(휴대폰에서 상세 페이지가 열리지 않으므로).
- 발송에 성공한 공고만 data/sent.json 에 기록한다(DRY_RUN·실패 시 기록하지 않음).
- 규칙을 바꾸면 evals/run_evals.py 를 다시 실행해 통과 여부를 확인한다.

## Done when
- offline 모드에서 그래프가 끝까지 실행되고 outbox 에 상세 페이지·카카오 미리보기가 생성된다.
- evals/run_evals.py 의 모든 항목이 PASS 다.
- 유효 공고가 MIN_ITEMS 미만이면 키워드를 넓혀 다시 거르는 루프가 동작한다.
- 마감 제외·중복 제거·필수값 검사가 동작한다.
- README 에 설치·실행·카카오·상세 페이지 공개 설정 방법이 있다.
