"""수집 대상 사이트별 파서. 네트워크는 쓰지 않는다(가져오기는 agent/tools.py 담당).

각 모듈은 두 가지를 제공한다.
- parse_list(...)   목록 원본 → 후보 공고 목록 (표준 스키마 + _ref)
- parse_detail(...) 상세 원본 → sections (rules/schedule/prize/overview/evaluation/data/consent)

sections 의 각 값은 {"html": 정리된 원문 HTML, "text": 평문} 이며, 원문에 없으면 빈 값이다.
"""

SECTION_KEYS = ("rules", "schedule", "prize", "overview", "evaluation", "data", "consent")
SECTION_LABELS = {
    "rules": "규칙/가이드라인",
    "schedule": "상세 일정",
    "prize": "상금 및 혜택",
    "overview": "대회 개요",
    "evaluation": "평가 기준",
    "data": "데이터 설명",
    "consent": "동의사항",
}
PRIORITY_KEYS = ("rules", "schedule", "prize")   # 사용자가 가장 먼저 보는 3항목
