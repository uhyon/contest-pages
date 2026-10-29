"""노드 = State 를 받아 State(의 일부)를 돌려주는 파이썬 함수.

[LLM] 표시 노드: 판단·언어 처리 (키가 없으면 규칙 기반으로 대체)
[CODE] 표시 노드: 규칙·검증·조립·발송 (항상 같은 결과)
"""
from __future__ import annotations

import json
import os
import re

from pydantic import BaseModel, Field

from . import render, rules, tools
from .sources import PRIORITY_KEYS
from .state import AgentState

MIN_ITEMS = int(os.getenv("MIN_ITEMS", "3"))            # 이보다 적으면 필터를 넓혀 다시 거른다
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "2"))       # 필터 라운드 최대 횟수
MAX_KAKAO_ITEMS = int(os.getenv("MAX_KAKAO_ITEMS", "5"))  # 카카오톡으로 보낼 공고 수 (나머지는 목록 페이지)

BROAD_KEYWORDS = ["AI", "인공지능", "머신러닝", "딥러닝", "데이터", "ML", "LLM", "에이전트", "Agent", "빅데이터"]
# LLM 이 없을 때 관심 분야 → 제목·태그에서 찾을 키워드
INTEREST_KEYWORDS = {
    "AI 개발": ["AI 개발", "AI 에이전트", "AI Agent", "LLM", "생성형"],
    "데이터 분석": ["데이터 분석", "데이터분석", "빅데이터", "분석 모델"],
    "머신러닝": ["머신러닝", "딥러닝", "ML", "예측", "탐지 모델"],
}


# =============================================================== 1. 필터 키워드 [LLM]
class Keywords(BaseModel):
    keywords: list[str] = Field(description="공고 제목·태그에서 찾을 짧은 키워드 (한국어/영어, 각 1~2단어)")


def plan_filters(state: AgentState) -> dict:
    interests = state.get("interests") or ["AI 개발", "데이터 분석", "머신러닝"]
    kws = list(dict.fromkeys(k for i in interests for k in INTEREST_KEYWORDS.get(i, [i])))
    llm = tools.get_llm()
    if llm:
        prompt = (f"관심 분야: {interests}\n공모전·해커톤 공고 제목과 태그에서 이 분야 공고를 고르기 위한 "
                  "키워드 6~10개를 만들어라. 관심 분야 단어와 동의어·영문 표기(예: 머신러닝→ML)만 넣고, "
                  "'대회' '공모전'처럼 모든 공고에 들어가는 단어는 넣지 마라.")
        kws = list(dict.fromkeys(interests + llm.with_structured_output(Keywords).invoke(prompt).keywords))
    return {"interests": interests, "keywords": kws, "attempt": 1, "log": [f"[plan] 키워드 {kws}"]}


# =============================================================== 2. 사이트 수집 [CODE/도구]
def collect(state: AgentState) -> dict:
    listings, logs = [], []
    for src in tools.enabled_sources():
        try:
            rows = tools.fetch_listing(src)
            listings += rows
            logs.append(f"[collect] {src}: {len(rows)}건")
        except Exception as e:   # 사이트 하나가 죽어도 나머지는 계속
            logs.append(f"[collect] {src}: 실패 ({type(e).__name__}: {e})")
    return {"listings": listings, "log": logs}


# =============================================================== 3. 범위·키워드 필터 [CODE]
def filter_listings(state: AgentState) -> dict:
    listings, kws = state.get("listings", []), state["keywords"]
    contests = [x for x in listings if rules.is_contest(x)]
    candidates = [x for x in contests if rules.matches_keywords(x, kws)]
    return {"candidates": candidates,
            "log": [f"[filter] round {state.get('attempt', 1)}: 전체 {len(listings)} → 대회 {len(contests)} "
                    f"→ 키워드 일치 {len(candidates)}"]}


# =============================================================== 4. 검증 [CODE]
def validate(state: AgentState) -> dict:
    valid, rejected = rules.validate_items(state.get("candidates", []), state["today"])
    counts = rules.reason_counts(rejected)
    return {"valid": valid, "rejected": rejected,
            "log": [f"[validate] valid {len(valid)} / rejected {len(rejected)} {counts}"]}


def route_after_validate(state: AgentState) -> str:
    """조건부 엣지: 충분하면 상세 수집, 부족하고 기회가 남으면 키워드를 넓혀 다시 거른다."""
    if len(state.get("valid", [])) >= MIN_ITEMS:
        return "details"
    if state.get("attempt", 1) < MAX_ATTEMPTS:
        return "broaden"
    return "details"   # 기회를 다 썼으면 있는 만큼(0건이면 안내 메시지)


# =============================================================== 5. 키워드 넓히기 [LLM]
def broaden_filters(state: AgentState) -> dict:
    kws, llm = state["keywords"], tools.get_llm()
    if llm:
        prompt = (f"현재 키워드: {kws}\n관심 분야: {state.get('interests')}\n"
                  f"유효 공고가 {len(state.get('valid', []))}건뿐이다. 관심 분야와 가까운 AI·데이터 공고까지 "
                  "잡히도록 더 넓은 키워드 6~10개를 만들어라.")
        extra = llm.with_structured_output(Keywords).invoke(prompt).keywords
    else:
        extra = BROAD_KEYWORDS
    new = list(dict.fromkeys(kws + extra))
    attempt = state.get("attempt", 1) + 1
    return {"keywords": new, "attempt": attempt, "log": [f"[broaden] round {attempt} 키워드 {new}"]}


# =============================================================== 6. 상세 수집 [CODE/도구]
def fetch_details(state: AgentState) -> dict:
    out, failed = [], 0
    for v in state.get("valid", []):
        v = dict(v)
        try:
            d = tools.fetch_detail(v.get("_ref") or {})
        except Exception:
            d, failed = {"sections": {}, "facts": {}}, failed + 1
        v["sections"] = {**(v.pop("_sections", None) or {}), **{k: s for k, s in d["sections"].items() if s.get("html")}}
        v["_facts"] = d["facts"]
        if v.get("target", "기타") == "기타" and d["facts"].get("target"):
            v["target"] = d["facts"]["target"]
        out.append(v)
    return {"valid": out, "log": [f"[details] {len(out)}건 상세 수집" + (f", 실패 {failed}건(정보 없음 처리)" if failed else "")]}


# =============================================================== 7. 핵심 한 줄 요약 [LLM]
class Summary(BaseModel):
    rules: str = Field(description="참가 규칙 핵심 (팀 인원 등). 40자 이내. 원문에 없으면 '정보 없음'")
    schedule: str = Field(description="가장 중요한 마감 일시와 다음 일정. 40자 이내. 원문에 없으면 '정보 없음'")
    prize: str = Field(description="총 상금과 주요 혜택. 40자 이내. 원문에 없으면 '정보 없음'")


SUMMARY_RULES = """너는 공모전 공고 요약기다. 아래 세 섹션 원문만 보고 각 항목을 한 줄(40자 이내)로 요약하라.
- 원문에 있는 숫자·날짜·금액만 쓴다. 없으면 정확히 '정보 없음'이라고 쓴다. 추측하지 않는다.
- 링크·기관명은 쓰지 않는다."""


def _fallback_summary(v: dict) -> dict:
    sec, facts = v.get("sections") or {}, v.get("_facts") or {}
    text = lambda k: (sec.get(k) or {}).get("text", "")
    return {"rules": rules.rules_line(facts, text("rules")),
            "schedule": rules.schedule_line(v, facts),
            "prize": rules.prize_line(facts, text("prize"), v.get("prize_hint", ""))}


def summarize(state: AgentState) -> dict:
    llm, out, replaced = tools.get_llm(), [], 0
    for v in state.get("valid", []):
        v = dict(v)
        base = _fallback_summary(v)
        summary = dict(base)
        if llm:
            sec = v.get("sections") or {}
            src = "\n\n".join(f"[{k}]\n{(sec.get(k) or {}).get('text', '')[:2500]}" for k in PRIORITY_KEYS)
            got = llm.with_structured_output(Summary).invoke(f"{SUMMARY_RULES}\n\n제목: {v['title']}\n{src}").model_dump()
            ground = src + json.dumps(v.get("_facts") or {}, ensure_ascii=False) + str(v.get("raw_date", ""))
            for k in PRIORITY_KEYS:
                line = (got.get(k) or "").strip()[: rules.SUMMARY_MAX]
                # 숫자가 원문에 없거나, 코드가 찾은 정보를 LLM 이 '정보 없음'으로 지우면 코드 값을 쓴다
                if line and rules.grounded(line, ground) and not (line == rules.NO_INFO and base[k] != rules.NO_INFO):
                    summary[k] = line
                else:
                    replaced += 1
        v["summary"] = summary
        out.append(v)
    note = f", 근거 없는 LLM 요약 {replaced}개를 규칙 값으로 교체" if replaced else ""
    return {"valid": out, "log": [f"[summarize] {len(out)}건 핵심 한 줄 작성 ({'LLM' if llm else '규칙 기반'}){note}"]}


# =============================================================== 8. 상세 페이지 조립 [CODE]
def build_pages(state: AgentState) -> dict:
    today, out = state["today"], []
    d = tools.pages_dir(today)
    for v in state.get("valid", []):
        v = dict(v)
        name = render.slug(v)
        v["detail_id"], v["detail_url"] = name, tools.page_url(today, name)
        tools.write_text(d / name, render.detail_page(v))
        out.append(v)
    index = tools.write_text(d / "index.html", render.index_page(out, today))
    return {"valid": out, "pages_dir": str(d), "preview_path": index,
            "log": [f"[pages] 상세 페이지 {len(out)}개 + 목록 페이지 → {d}"]}


# =============================================================== 9. 새 공고만 고르기 [CODE]
def select_new(state: AgentState) -> dict:
    """이미 카카오톡으로 보낸 공고(data/sent.json)는 빼고 새 공고만 남긴다. 상세·목록 페이지에는 전부 남긴다."""
    new, old = rules.split_new(state.get("valid", []), tools.load_sent())
    return {"new_items": new, "log": [f"[select_new] 새 공고 {len(new)}건 / 이미 보낸 공고 {len(old)}건 제외"]}


# =============================================================== 10. 카카오톡 메시지 조립 [CODE]
def compose_kakao(state: AgentState) -> dict:
    valid, new, today = state.get("valid", []), state.get("new_items", []), state["today"]
    shown = new[:MAX_KAKAO_ITEMS]
    index_url = tools.page_url(today, "index.html")
    msgs = [{"_kind": "header", "_index_url": index_url,
             "template": render.kakao_header(valid, new, len(shown), today, index_url)}]
    msgs += [{"_kind": "item", "template": render.kakao_item(v)} for v in shown]
    return {"kakao_messages": msgs, "log": [f"[compose] 카카오톡 메시지 {len(msgs)}개 (헤더 1 + 새 공고 {len(shown)})"]}


# =============================================================== 11. 발송 전 리뷰 [CODE]
def _will_send() -> bool:
    return os.getenv("DRY_RUN", "1") != "1" and tools.kakao_ready()


def review(state: AgentState) -> dict:
    secrets = tools.secret_values()
    valid, msgs = state.get("valid", []), state.get("kakao_messages", [])
    errors = rules.review_kakao(msgs, valid, state.get("new_items", []), MAX_KAKAO_ITEMS, secrets)
    d = tools.pages_dir(state["today"])
    for v in valid:
        errors += rules.review_page((d / v["detail_id"]).read_text(encoding="utf-8"), v, secrets)
    base = os.getenv("PAGES_BASE_URL", "")
    if _will_send() and not base:
        errors.append("PAGES_BASE_URL 미설정: 휴대폰에서 상세 페이지 링크가 열리지 않음")
    elif base and not re.match(r"^https?://[^\s=]+$", base):
        errors.append(f"PAGES_BASE_URL 형식 오류(http(s):// 로 시작하는 주소여야 함): {base!r}")

    # 사람이 검토할 수 있게 카카오톡 미리보기를 저장한다
    preview = "\n\n".join(
        m["template"]["text"] + "".join(f"\n  [{b['title']}] {b['link']['web_url']}" for b in m["template"].get("buttons", []))
        for m in msgs)
    path = tools.write_text(tools.ROOT / "outbox" / f"kakao_{state['today']}.txt", preview)
    return {"review_errors": errors,
            "log": [f"[review] {'PASS' if not errors else 'FAIL ' + str(errors)} · 카카오 미리보기 {path} · 목록 {state.get('preview_path')}"]}


def route_after_review(state: AgentState) -> str:
    return "send" if not state.get("review_errors") else "abort"


# =============================================================== 12. 상세 페이지 공개 [CODE/도구]
def publish(state: AgentState) -> dict:
    """PAGES_PUBLISH=git 이면 페이지를 푸시하고 GitHub Pages 반영을 기다린다 (카톡 링크가 바로 열리게).
    그래프는 이 노드 '직전'에 멈춘다(interrupt_before). 사람이 승인해야 공개·발송이 진행된다."""
    if not (_will_send() and tools.publish_enabled()):
        return {"log": ["[publish] 건너뜀 (PAGES_PUBLISH=git 이고 실제 발송일 때만 자동 공개)"]}
    result = tools.publish_pages(state["today"], tools.page_url(state["today"], "index.html"))
    return {"log": [f"[publish] 페이지 푸시 완료, GitHub Pages 반영 {result}"]}


# =============================================================== 13. 발송 [CODE]
def send(state: AgentState) -> dict:
    if not _will_send():
        why = "DRY_RUN=1" if os.getenv("DRY_RUN", "1") == "1" else "카카오 토큰 없음"
        return {"sent": False, "status": "dry_run", "log": [f"[send] {why}: 실제 발송하지 않고 미리보기만 저장"]}
    n = tools.kakao_send([m["template"] for m in state["kakao_messages"]])
    # 실제로 보낸 공고만 기록한다 (MAX_KAKAO_ITEMS 를 넘어 못 보낸 공고는 다음에 새 공고로 다시 나온다)
    sent = tools.load_sent()
    for v in state.get("new_items", [])[:MAX_KAKAO_ITEMS]:
        sent[rules.sent_key(v)] = {"title": v["title"], "end_date": v["end_date"], "sent_at": state["today"]}
    tools.save_sent(sent)
    return {"sent": True, "status": "sent", "log": [f"[send] 카카오톡 나에게 보내기 {n}개 완료 · 보낸 기록 {len(sent)}건"]}


def abort(state: AgentState) -> dict:
    return {"sent": False, "status": "aborted", "log": [f"[abort] 리뷰 실패로 발송 중단: {state.get('review_errors')}"]}
