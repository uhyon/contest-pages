"""DACON (dacon.io) — 목록·상세 모두 페이지 HTML 안의 __NUXT__ 데이터를 읽는다."""
from __future__ import annotations

import json

from .html_clean import clean_html, to_text
from .nuxt import parse_nuxt

BASE = "https://dacon.io"
LIST_URL = f"{BASE}/competitions"


def detail_url(cpt_id) -> str:
    return f"{BASE}/competitions/official/{cpt_id}/overview/description"


def _category(name: str) -> str:
    for word, cat in (("해커톤", "해커톤"), ("공모전", "공모전"), ("챌린지", "경진대회"), ("경진대회", "경진대회")):
        if word in name:
            return cat
    return "경진대회"


def parse_list(page_html: str) -> list[dict]:
    data = (parse_nuxt(page_html).get("data") or [{}])[0]
    out = []
    for c in data.get("compData") or []:
        if not c.get("cpt_id") or not c.get("name"):
            continue
        name = c["name"].strip()
        out.append({
            "title": name,
            # DACON 목록에는 주최 기관이 비어 있는 경우가 많다 → 운영 플랫폼(DACON)을 표시한다
            "provider": (c.get("sponsor") or "").strip() or "DACON",
            "category": _category(name),
            "target": "기타",
            "start_date": str(c.get("period_start") or "")[:10],
            "raw_date": str(c.get("period_end") or ""),
            "url": detail_url(c["cpt_id"]),
            "source_name": "dacon",
            "keywords": c.get("keyword") or "",
            "prize_hint": (c.get("prize_info") or "").strip(),
            "_ref": {"source": "dacon", "id": c["cpt_id"]},
        })
    return out


def _timeline(raw) -> list[dict]:
    """'[{"2026-10-12":"대회 시작"}, ...]' → [{date, label}]"""
    try:
        rows = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except json.JSONDecodeError:
        return []
    return [{"date": d, "label": str(label)} for row in rows if isinstance(row, dict) for d, label in row.items()]


def parse_detail(page_html: str) -> dict:
    nuxt = parse_nuxt(page_html)
    detail = {}
    for v in (nuxt.get("fetch") or {}).values():
        if isinstance(v, dict) and isinstance(v.get("competitionDetail"), dict):
            detail = v["competitionDetail"]
            break
    if not detail:
        return {"sections": {}, "facts": {}}

    raw = {"rules": detail.get("rule"), "schedule": detail.get("schedule"), "prize": detail.get("prize_text"),
           "overview": detail.get("description"), "evaluation": detail.get("evaluation_rule"),
           "data": detail.get("data_explain"), "consent": detail.get("agreement")}
    sections = {}
    for k, v in raw.items():
        h = clean_html(v, BASE)
        sections[k] = {"html": h, "text": to_text(h)}
    facts = {
        "team_max": detail.get("max_team_member"),
        "prize_hint": (detail.get("prize_info") or "").strip(),
        "timeline": _timeline(detail.get("time_line_data")),
    }
    return {"sections": sections, "facts": facts}
