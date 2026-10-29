---
name: kakao-release
description: 조립된 카카오톡 메시지와 상세 페이지가 발송 가능한 수준인지 최종 점검할 때 사용
---

# Goal
잘못된 메시지·페이지가 실제 사용자에게 나가지 않도록 발송 직전에 점검한다.

# Trigger
- review 노드 (compose_kakao 다음, send 이전)

# Required checks (rules.review_kakao / rules.review_page)
- 카카오 공고 메시지 수 = min(valid 수, MAX_KAKAO_ITEMS)
- 메시지 본문이 200자 이하인가
- 모든 링크가 valid 의 원문 url · 상세 페이지 url · 목록 페이지 url 중 하나인가 (지어낸 링크 없음)
- 공고 메시지마다 상세 페이지 링크와 원문 링크가 둘 다 있는가
- 상세 페이지에 원문 링크·provider·target·end_date 가 있는가
- 상세 페이지에서 규칙 → 일정 → 상금 → (나머지) 순서인가
- 비밀 값(API 키·토큰)이 메시지·페이지에 없는가
- 0건일 때 안내 문구가 들어갔는가
- 실제 발송이면 PAGES_BASE_URL 이 설정돼 있는가

# Procedure
1. kakao_messages 와 valid, 상세 페이지 파일을 비교한다.
2. 실패 항목을 review_errors 에 적는다.
3. outbox/kakao_YYYY-MM-DD.txt 에 미리보기를 저장한다.
4. review_errors 가 비어 있으면 approve(사람 승인) 단계로, 있으면 abort 로 보낸다.

# Output
- ready / not ready 판정
- review_errors 목록
