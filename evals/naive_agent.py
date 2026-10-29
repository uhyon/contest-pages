"""하네스 OFF 기준선 — "해커톤 사이트에서 AI 공모전 찾아서 카톡으로 보내줘" 한 줄 요구만 구현한 버전.

검증·재필터·리뷰·승인 없이 목록을 그대로 카카오톡 메시지로 만든다.
겉보기엔 동작하지만 무엇이 빠졌는지 evals 로 확인한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import tools  # noqa: E402


def run(today: str) -> dict:
    items = [x for s in tools.ALL_SOURCES for x in tools.fetch_listing(s)]
    msgs = [{"_kind": "item", "template": {"object_type": "text", "text": f"{x['title']}\n{x['raw_date']}",
                                           "link": {"web_url": x["url"], "mobile_web_url": x["url"]}}}
            for x in items]
    return {"kakao_messages": msgs, "status": "sent", "attempt": 1, "items": items, "review_errors": ["(리뷰 없음)"]}
