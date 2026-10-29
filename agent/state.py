"""그래프 State 정의 — 노드와 노드 사이를 오가는 '택배 상자'.

AGENTS.md 의 표준 스키마(Contest)와 필드 이름을 반드시 맞춘다.
"""
import operator
from typing import Annotated, TypedDict


class Section(TypedDict, total=False):
    html: str          # 원문 섹션을 정리한 HTML (없으면 빈 값 → '정보 없음')
    text: str          # 평문 (요약·근거 검사용)


class Contest(TypedDict, total=False):
    title: str
    provider: str
    category: str      # 공모전 | 해커톤 | 경진대회 | 기타
    target: str        # 학생 | 일반 | 스타트업 | 개발자 | 기타
    start_date: str    # YYYY-MM-DD
    end_date: str      # YYYY-MM-DD
    url: str           # 원문 공고 링크
    source_name: str   # dacon | daker | dev_event | fixture
    raw_date: str
    keywords: str      # 키워드 필터용 (사이트 태그·한 줄 소개)
    # validate 단계에서 코드가 채우는 값
    days_left: int
    badge: str
    reason: str        # rejected 일 때 사유
    # 상세 단계에서 채우는 값
    sections: dict[str, Section]   # rules/schedule/prize/overview/evaluation/data/consent
    summary: dict[str, str]        # rules/schedule/prize 핵심 한 줄 (카카오톡용)
    detail_id: str
    detail_url: str                # 상세 페이지(HTML) 주소


class AgentState(TypedDict, total=False):
    # 입력
    interests: list[str]           # 관심 분야 예: ["AI 개발", "데이터 분석", "머신러닝"]
    today: str                     # YYYY-MM-DD (평가 재현성을 위해 주입 가능)

    # 수집·필터 루프
    listings: list[Contest]        # 사이트에서 가져온 전체 목록 (한 번만 수집)
    keywords: list[str]            # 이번 라운드 필터 키워드
    attempt: int                   # 필터 라운드 (1부터)
    candidates: list[Contest]
    valid: list[Contest]
    rejected: list[Contest]

    # 카카오톡 + 상세 페이지
    pages_dir: str
    new_items: list[Contest]       # 아직 카카오톡으로 보낸 적 없는 공고 (data/sent.json 기준)
    kakao_messages: list[dict]     # 카카오톡 템플릿(text) 목록
    review_errors: list[str]
    preview_path: str
    sent: bool
    status: str                    # sent | dry_run | aborted

    # 실행 로그(누적)
    log: Annotated[list[str], operator.add]
