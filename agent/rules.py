"""코드가 맡는 규칙 — AGENTS.md 'Data quality rules' 를 그대로 구현한다.

LLM에게 맡기지 않는 이유: 매번 같은 입력에 같은 결과가 나와야 하고,
evals 로 자동 검증할 수 있어야 하기 때문.
"""
from __future__ import annotations

import html
import re
from datetime import date, timedelta

REQUIRED = ("title", "provider", "end_date", "url")


def _year_for(month: int, day: int, today: date) -> int:
    """연도가 없는 날짜(예: '~11/30')는 오늘 이후 가장 가까운 날짜로 본다."""
    try:
        cand = date(today.year, month, day)
    except ValueError:
        return today.year
    return today.year if cand >= today - timedelta(days=31) else today.year + 1


def normalize_date(raw: str | None, today: date | None = None) -> str:
    """다양한 날짜 표기를 YYYY-MM-DD 로. 실패하면 빈 문자열."""
    if not raw:
        return ""
    today = today or date.today()
    s = str(raw).strip()

    # 기간 표기면 마지막 날짜(마감일)를 쓴다: "2026.10.01 ~ 2026.11.30"
    parts = re.split(r"\s*[~∼〜]\s*|\s+-\s+|\s+–\s+", s)
    s = parts[-1].strip() or s

    m = re.search(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?", s)
        if not m:
            return ""
        mo, d = map(int, m.groups())
        y = _year_for(mo, d, today)
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


_NOISE = re.compile(r"\[[^\]]*\]|\([^)]*\)|참가자\s*모집|참가팀\s*모집|모집\s*공고|모집|안내|공고")


def norm_title(title: str) -> str:
    """'[재공지] ... 공모전 참가자 모집' 같은 꾸밈말을 지우고 비교한다.
    (PLAN.md Risk: 단순 문자열 비교로는 중복 판정이 부족하다)"""
    t = _NOISE.sub("", str(title or ""))
    return re.sub(r"\s+", "", t).lower()


def dedupe_key(item: dict) -> str:
    provider = re.sub(r"\s+", "", str(item.get("provider") or "")).lower()
    return f"{provider}|{norm_title(item.get('title'))}|{item.get('end_date', '')}"


def badge_for(days_left: int) -> str:
    if days_left == 0:
        return "오늘 마감"
    if days_left <= 7:
        return "이번 주 마감"
    return ""


def validate_items(items: list[dict], today_str: str) -> tuple[list[dict], list[dict]]:
    """valid / rejected 로 나눈다. rejected 에는 reason 을 남긴다."""
    today = date.fromisoformat(today_str)
    valid, rejected, seen = [], [], set()

    for raw in items:
        it = dict(raw)
        if not it.get("end_date") and it.get("raw_date"):
            it["end_date"] = normalize_date(it["raw_date"], today)
        elif it.get("end_date"):
            it["end_date"] = normalize_date(it["end_date"], today) or ""

        if it.get("raw_date") and not it.get("end_date"):
            rejected.append({**it, "reason": "bad_date"})
            continue
        missing = [k for k in REQUIRED if not str(it.get(k, "")).strip()]
        if missing:
            rejected.append({**it, "reason": "missing_field:" + ",".join(missing)})
            continue
        if not re.match(r"^https?://", it["url"]):
            rejected.append({**it, "reason": "bad_url"})
            continue

        days_left = (date.fromisoformat(it["end_date"]) - today).days
        if days_left < 0:
            rejected.append({**it, "reason": "expired", "expired": True})
            continue

        # 같은 원문 링크도 중복으로 본다 (Dev-Event 가 DACON·DAKER 공고를 다른 주최명으로 재게시)
        key, url_key = dedupe_key(it), "url|" + it["url"].rstrip("/").lower()
        if key in seen or url_key in seen:
            rejected.append({**it, "reason": "duplicate"})
            continue
        seen.update((key, url_key))

        it["days_left"] = days_left
        it["badge"] = badge_for(days_left)
        it.setdefault("target", "기타")
        it.setdefault("category", "기타")
        valid.append(it)

    valid.sort(key=lambda x: x["days_left"])
    return valid, rejected


def reason_counts(rejected: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rejected:
        k = r.get("reason", "unknown").split(":")[0]
        out[k] = out.get(k, 0) + 1
    return out


# ------------------------------------------------------------------ 수집 범위 필터
def _squash(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def is_contest(item: dict) -> bool:
    """Dev-Event 는 세미나·모임도 섞여 있으므로 '대회' 태그만 공모전으로 본다."""
    if item.get("source_name") == "dev_event":
        return "대회" in (item.get("tags") or [])
    return True


def matches_keywords(item: dict, keywords: list[str]) -> bool:
    """제목·키워드·태그에 키워드 하나라도 있으면 통과 (공백·대소문자 무시)."""
    hay = _squash(" ".join([item.get("title", ""), item.get("keywords", ""), " ".join(item.get("tags") or [])]))
    return any(_squash(k) and _squash(k) in hay for k in keywords)


# ------------------------------------------------------------------ 핵심 한 줄 (카카오톡용)
NO_INFO = "정보 없음"
SUMMARY_MAX = 40
WEEKDAY = "월화수목금토일"


def _mmdd(dt: str) -> str:
    """'2026-11-12 10:00' → '11/12(목) 10:00'"""
    try:
        d = date.fromisoformat(dt[:10])
    except ValueError:
        return dt
    tm = dt[11:16] if len(dt) >= 16 and dt[11:16] not in ("", "00:00") else ""
    return f"{d.month}/{d.day}({WEEKDAY[d.weekday()]})" + (f" {tm}" if tm else "")


def grounded(line: str, source: str) -> bool:
    """요약 문장의 숫자가 모두 원문에 있어야 한다 (LLM 이 날짜·금액을 지어내는 것 차단).
    '정보 없음' 은 항상 허용."""
    if not line or line == NO_INFO:
        return True
    src = re.sub(r"(?<=\d),(?=\d)", "", source or "")
    nums = re.findall(r"\d+", re.sub(r"(?<=\d),(?=\d)", "", line))
    src_nums = set(re.findall(r"\d+", src))
    return all(n in src_nums or n.lstrip("0") in src_nums for n in nums)


def rules_line(facts: dict, rules_text: str) -> str:
    n = facts.get("team_max")
    if not n:
        m = re.search(r"최대\s*(?:인원\s*[:：]?\s*)?(\d+)\s*(?:인|명)", rules_text or "")
        n = m and m.group(1)
    if n:
        return "개인 참가만 가능" if str(n) == "1" else f"개인/팀 참가 · 팀 최대 {n}인"
    return NO_INFO


def deadline_of(item: dict) -> str:
    """원문이 'YYYY-MM-DD HH:MM' 형식이면 시각까지, 아니면 end_date 만."""
    raw = str(item.get("raw_date") or "")
    return raw[:16] if raw[:10] == item.get("end_date") else item.get("end_date", "")


def schedule_line(item: dict, facts: dict) -> str:
    """마감 일시 + (있으면) 마감 뒤 가장 가까운 다음 일정 1개."""
    if not item.get("end_date"):
        return NO_INFO
    line = f"마감 {_mmdd(deadline_of(item))}"
    nxt = [t for t in facts.get("timeline") or [] if t.get("date", "")[:10] > item["end_date"]]
    if nxt:
        line += f" · {nxt[0]['label']} {_mmdd(nxt[0]['date'][:10])}"
    return line[:SUMMARY_MAX]


def prize_line(facts: dict, prize_text: str, hint: str = "") -> str:
    p = re.sub(r"\s+", "", facts.get("prize_hint") or hint or "")
    if p and p not in ("-", "0"):
        return f"총 {p}" if re.search(r"\d", p) else p
    m = re.search(r"총\s*상금\s*[:：]?\s*([\d,]+\s*(?:만\s*)?원)", prize_text or "")
    return "총 " + re.sub(r"\s+", "", m.group(1)) if m else NO_INFO


# ------------------------------------------------------------------ 이미 보낸 공고
def sent_key(item: dict) -> str:
    """보낸 기록의 키 = 원문 url (끝 '/'·대소문자 무시)."""
    return item["url"].rstrip("/").lower()


def split_new(valid: list[dict], sent: dict) -> tuple[list[dict], list[dict]]:
    """valid → (새 공고, 이미 보낸 공고). 순서(마감 임박 순)는 그대로 유지."""
    new = [v for v in valid if sent_key(v) not in sent]
    old = [v for v in valid if sent_key(v) in sent]
    return new, old


# ------------------------------------------------------------------ 발송 전 리뷰
KAKAO_TEXT_MAX = 200   # 카카오 기본 텍스트 템플릿 본문 최대 길이


def _template_links(t: dict) -> list[str]:
    links = [t.get("link", {}).get("web_url", ""), t.get("link", {}).get("mobile_web_url", "")]
    for b in t.get("buttons") or []:
        links += [b.get("link", {}).get("web_url", ""), b.get("link", {}).get("mobile_web_url", "")]
    return [l for l in links if l]


def review_kakao(messages: list[dict], valid: list[dict], new_items: list[dict], max_items: int,
                 secrets: list[str] | None = None) -> list[str]:
    """kakao-release 스킬의 Required checks. new_items = 이번에 처음 보내는 공고."""
    errors = []
    shown = new_items[:max_items]
    items = [m for m in messages if m.get("_kind") == "item"]
    if len(items) != len(shown):
        errors.append(f"카카오 공고 메시지 수({len(items)}) != 보낼 공고 수({len(shown)})")
    allowed = {v["url"] for v in valid} | {v.get("detail_url") for v in valid if v.get("detail_url")}
    allowed |= {m.get("_index_url") for m in messages if m.get("_index_url")}
    for i, m in enumerate(messages):
        t = m["template"]
        if len(t.get("text", "")) > KAKAO_TEXT_MAX:
            errors.append(f"메시지 {i} 본문 {len(t['text'])}자 > {KAKAO_TEXT_MAX}자")
        unknown = [l for l in _template_links(t) if l not in allowed]
        if unknown:
            errors.append(f"메시지 {i} 검증되지 않은 링크: {unknown[:2]}")
        for s in secrets or []:
            if s and len(s) > 6 and s in str(t):
                errors.append(f"메시지 {i} 에 비밀 값 노출")
    for m, v in zip(items, shown):
        links = _template_links(m["template"])
        if v["url"] not in links:
            errors.append(f"원문 링크 누락: {v['title']}")
        if v.get("detail_url") and v["detail_url"] not in links:
            errors.append(f"상세 페이지 링크 누락: {v['title']}")
    if not valid and not any("조건에 맞는 공고가 없습니다" in m["template"].get("text", "") for m in messages):
        errors.append("0건 안내 문구 누락")
    return errors


def review_page(page_html: str, item: dict, secrets: list[str] | None = None) -> list[str]:
    """상세 페이지: 원문 링크·필수 표시값·우선 3항목 순서·비밀 값."""
    errors = []
    title = item.get("title", "")
    if f'href="{item["url"]}"' not in page_html.replace("&amp;", "&"):
        errors.append(f"[{title}] 상세 페이지에 원문 링크 없음")
    target = item.get("target") if item.get("target") not in (None, "", "기타") else NO_INFO
    for k, val in (("provider", item.get("provider", "")), ("target", target), ("end_date", item.get("end_date", ""))):
        if html.escape(str(val)) not in page_html:
            errors.append(f"[{title}] 상세 페이지에 {k} 표시 없음")
    pos = [page_html.find(f'id="sec-{k}"') for k in ("rules", "schedule", "prize", "overview")]
    if -1 in pos or pos != sorted(pos):
        errors.append(f"[{title}] 우선 3항목(규칙·일정·상금)이 맨 앞에 있지 않음")
    for s in secrets or []:
        if s and len(s) > 6 and s in page_html:
            errors.append(f"[{title}] 상세 페이지에 비밀 값 노출")
    return errors
