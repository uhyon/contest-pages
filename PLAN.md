# PLAN.md

## Task
AI 공모전·해커톤 수집(DACON·DAKER·Dev-Event) → 검증 → 카카오톡 핵심 알림 + 상세 페이지 LangGraph 에이전트 MVP

## Milestones
| # | 단계 | 산출물 | 성공 기준 |
|---|---|---|---|
| 1 | 표준 스키마·State 정의 | agent/state.py | Contest 필드가 AGENTS.md 와 일치, sections/summary 포함 |
| 2 | 규칙 함수 구현 | agent/rules.py | evals 규칙 테스트 PASS |
| 3 | 사이트 파서 | agent/sources/ | 실제 사이트 응답 + fixture 둘 다 파싱 |
| 4 | 도구 연결(HTTP·LLM·카카오) | agent/tools.py | 키 없으면 offline / dry-run 으로 자동 전환 |
| 5 | 출력물 조립 | agent/render.py | 상세 페이지 3항목 우선, 카톡 200자·링크 2개 |
| 6 | 노드·그래프 | agent/nodes.py, graph.py | 조건부 엣지 2개(재필터, 리뷰 게이트), 승인 전 interrupt |
| 7 | 평가 실행 | evals/run_evals.py | 전체 PASS, 하네스 OFF 기준선보다 높은 점수 |
| 8 | 문서화 | README.md, checklist.md | 설치·실행·카카오·페이지 공개 방법 기재 |

## Risks
- 사이트 구조 변경 (DACON __NUXT__, DAKER API, Dev-Event 마크다운) → 사이트별 파서 분리, 실패한 사이트는 건너뛰고 로그
- 같은 공고가 여러 사이트에 재게시 (Dev-Event ↔ DACON·DAKER, 주최명 표기 다름) → 원문 url 동일 여부도 중복으로 판정
- 연도 없는 날짜(Dev-Event '11. 12(목)') → 월 섹션 제목의 연도 사용
- LLM 이 한 줄 요약에 없는 날짜·금액을 지어냄 → 숫자 근거 검사(grounded), 실패 시 규칙 값
- 원문 HTML 에 스크립트·외부 위험 링크 → 허용 태그만 남기는 정리기
- 카카오 메시지 200자 제한·등록 안 된 링크 도메인 → 길이 검사, README 에 도메인 등록 안내
- 상세 페이지가 휴대폰에서 안 열림 → 실제 발송 시 PAGES_BASE_URL 필수(리뷰에서 차단)
- 재필터 무한 루프 → MAX_ATTEMPTS + recursion_limit
- 잘못된 메시지가 실제로 발송됨 → DRY_RUN 기본값, review 게이트, 사람 승인 interrupt

## Verification
- python evals/run_evals.py  (규칙 단위 테스트 + offline 전체 그래프 + 하네스 OFF 비교)
- outbox/pages/*/index.html 과 outbox/kakao_*.txt 를 열어 사람이 확인
- checklist.md 체크
