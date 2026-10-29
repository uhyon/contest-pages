"""그래프 조립: 노드 등록 → 엣지 연결 → 조건부 엣지 → 체크포인터·interrupt 로 컴파일."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from . import nodes as n
from .state import AgentState


def build_graph(require_approval: bool = True):
    g = StateGraph(AgentState)

    # 1) 노드 등록: 이름(영문) ↔ 함수
    g.add_node("plan_filters", n.plan_filters)
    g.add_node("collect", n.collect)
    g.add_node("filter", n.filter_listings)
    g.add_node("validate", n.validate)
    g.add_node("broaden_filters", n.broaden_filters)
    g.add_node("fetch_details", n.fetch_details)
    g.add_node("summarize", n.summarize)
    g.add_node("build_pages", n.build_pages)
    g.add_node("select_new", n.select_new)
    g.add_node("compose_kakao", n.compose_kakao)
    g.add_node("review", n.review)
    g.add_node("publish", n.publish)
    g.add_node("send", n.send)
    g.add_node("abort", n.abort)

    # 2) 일반 엣지: 순서대로
    g.add_edge(START, "plan_filters")
    g.add_edge("plan_filters", "collect")
    g.add_edge("collect", "filter")
    g.add_edge("filter", "validate")

    # 3) 조건부 엣지 ①: 유효 공고가 부족하면 키워드를 넓혀 다시 거른다(순환)
    g.add_conditional_edges("validate", n.route_after_validate,
                            {"details": "fetch_details", "broaden": "broaden_filters"})
    g.add_edge("broaden_filters", "filter")

    g.add_edge("fetch_details", "summarize")
    g.add_edge("summarize", "build_pages")
    g.add_edge("build_pages", "select_new")
    g.add_edge("select_new", "compose_kakao")
    g.add_edge("compose_kakao", "review")

    # 4) 조건부 엣지 ②: 리뷰 게이트 — 통과해야만 발송
    g.add_conditional_edges("review", n.route_after_review, {"send": "publish", "abort": "abort"})
    g.add_edge("publish", "send")
    g.add_edge("send", END)
    g.add_edge("abort", END)

    # 5) 체크포인터(기억) + human-in-the-loop: 공개·발송(publish) 직전에 멈춘다
    return g.compile(checkpointer=MemorySaver(),
                     interrupt_before=["publish"] if require_approval else [])
