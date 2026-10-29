"""DAKER (daker.ai) — DACON 에서 해커톤을 누르면 열리는 사이트. 공개 JSON API 가 있다."""
from __future__ import annotations

import html as H
from datetime import datetime, timedelta, timezone

from .html_clean import clean_html, to_text

BASE = "https://daker.ai"
LIST_URL = f"{BASE}/api/hackathons/public-list?limit=50"
KST = timezone(timedelta(hours=9))


def detail_api(slug: str) -> str:
    return f"{BASE}/api/hackathons/{slug}"


def page_url(slug: str) -> str:
    return f"{BASE}/public/hackathons/{slug}"


def to_kst(iso: str | None) -> str:
    """'2026-11-12T01:00:00.000Z' → '2026-11-12 10:00' (KST). 실패하면 빈 문자열."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def _category(title: str, competition_type: str) -> str:
    if "해커톤" in title:
        return "해커톤"
    if "공모전" in title or competition_type == "idea":
        return "공모전"
    return "경진대회"


def _won(amount) -> str:
    """15000000 → '1,500만원'"""
    try:
        n = int(float(amount))
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    return f"{n // 10000:,}만원" if n % 10000 == 0 else f"{n:,}원"


def parse_list(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows or []:
        if r.get("isPrivate") or r.get("isPracticeMode") or not r.get("slug"):
            continue
        title = (r.get("title") or "").strip()
        out.append({
            "title": title,
            "provider": (r.get("organizerName") or "").strip(),
            "category": _category(title, r.get("competitionType") or ""),
            "target": "기타",
            "start_date": to_kst(r.get("startDate"))[:10],
            "raw_date": to_kst(r.get("registrationDeadline")),
            "url": page_url(r["slug"]),
            "source_name": "daker",
            "keywords": " ".join(filter(None, [r.get("tagline"), r.get("taskCategory")])),
            "prize_hint": _won(r.get("totalPrize")),
            "_ref": {"source": "daker", "id": r["slug"]},
        })
    return out


def _stages_html(stages: list[dict]) -> str:
    """일정 섹션이 비어 있으면 API 의 단계(stages) 데이터로 표를 만든다 (원문 데이터 그대로)."""
    rows = []
    for s in sorted(stages or [], key=lambda s: s.get("stageOrder") or 0):
        start, end = to_kst(s.get("startDate")), to_kst(s.get("endDate"))
        if not (s.get("name") and (start or end)):
            continue
        rows.append(f"<tr><td>{H.escape(s['name'])}</td><td>{start} ~ {end}</td></tr>")
    return f"<table><tr><th>단계</th><th>기간 (KST)</th></tr>{''.join(rows)}</table>" if rows else ""


def parse_detail(d: dict) -> dict:
    target = {"anyone": "일반", "student": "학생", "students": "학생"}.get(d.get("eligibility") or "", "기타")
    schedule_html = clean_html(d.get("schedule"), BASE) or _stages_html(d.get("stages"))
    raw = {"rules": d.get("rules"), "prize": d.get("prizeDescription"), "overview": d.get("description"),
           "evaluation": d.get("evaluationCriteria"), "data": d.get("dataDescription"),
           "consent": d.get("consentTerms")}
    sections = {k: {"html": clean_html(v, BASE)} for k, v in raw.items()}
    sections["schedule"] = {"html": schedule_html}
    for s in sections.values():
        s["text"] = to_text(s["html"])
    timeline = [{"date": to_kst(s.get("endDate")), "label": s.get("name")}
                for s in d.get("stages") or [] if s.get("name") and s.get("endDate")]
    facts = {"team_max": d.get("maxTeamSize"), "prize_hint": _won(d.get("totalPrize")),
             "timeline": sorted(timeline, key=lambda t: t["date"]), "target": target}
    return {"sections": sections, "facts": facts}
