---
name: source-intake
description: 수집 사이트(DACON·DAKER·Dev-Event)의 목록·상세를 표준 스키마와 섹션으로 정규화할 때 사용
---

# Goal
사이트 목록을 표준 스키마의 공고 목록으로, 상세를 7개 섹션(규칙·일정·상금·개요·평가·데이터·동의)으로 변환한다.

# Trigger
- collect / fetch_details 노드가 실행될 때마다
- 새 수집 사이트를 추가하거나 사이트 구조가 바뀌었을 때 (agent/sources/ 에 파서 추가)

# Standard schema
- title        공고명
- provider     주최·주관 기관
- category     공모전 | 해커톤 | 경진대회 | 기타
- target       학생 | 일반 | 스타트업 | 개발자 | 기타
- start_date   접수 시작일 (YYYY-MM-DD, 없으면 빈 값)
- end_date     접수 마감일 (YYYY-MM-DD)
- url          원문 공고 링크 (절대경로)
- source_name  수집 사이트 (dacon | daker | dev_event)
- raw_date     정규화 전 날짜 원문

# Procedure
1. 목록 1건씩 읽는다. 사이트의 구조화된 필드(JSON·__NUXT__·마크다운 항목)를 그대로 옮긴다.
2. 공모전이 아닌 항목(Dev-Event 의 세미나·모임, 비공개·연습 대회)은 rules.is_contest / 파서에서 제외한다.
3. 각 필드를 본문에서 그대로 찾아 채운다. 본문에 없으면 빈 값으로 둔다(추측 금지).
4. 날짜는 원문을 raw_date 에 두고, rules.normalize_date 로 end_date 를 만든다.
5. url 은 사이트 데이터로 만든 원문 주소를 그대로 쓴다(새로 만들지 않는다).
5-1. 섹션은 원문 HTML 을 html_clean.clean_html 로 정리만 하고 내용은 바꾸지 않는다. 없으면 빈 값('정보 없음').
6. 결과를 validate 노드로 넘긴다.

# Quality bar
- 필수 필드 누락 비율이 30%를 넘으면 사이트 구조가 바뀐 것으로 보고 파서를 점검한다.
- 날짜 파싱 실패 건은 rejected(reason=bad_date)로 남기고 raw_date 를 보존한다.

# Deliverables
- candidates 목록 (State)
- 추출 실패 사유 로그
