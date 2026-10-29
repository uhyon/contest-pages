"""Dev-Event (github.com/brave-people/Dev-Event) — README.md 마크다운 목록.

형식:
## `26년 11월`
- __[행사명](링크)__
  - 분류: `온라인`, `무료`, `대회`, `AI`
  - 주최: 기관
  - 접수: 10. 01(목) 12:00 ~ 10. 30(금) 16:00     (또는 '일시:')

상세 페이지가 사이트마다 달라서 상세 섹션은 수집하지 않는다(일정만 목록에서 채운다).
"""
from __future__ import annotations

import html as H
import re

LIST_URL = "https://raw.githubusercontent.com/brave-people/Dev-Event/master/README.md"

_MONTH = re.compile(r"^##\s*`?(\d{2})년\s*(\d{1,2})월`?")
_ITEM = re.compile(r"^-\s*__\[(?P<title>.+?)\]\((?P<url>[^)\s]*)\)__")
_FIELD = re.compile(r"^\s+-\s*(?P<key>분류|주최|접수|일시)\s*:\s*(?P<val>.+)$")


def _category(title: str) -> str:
    for word in ("해커톤", "공모전", "경진대회"):
        if word in title:
            return word
    return "경진대회" if "대회" in title else "기타"


_DATE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})(?:\([^)]*\))?\s*(\d{1,2}:\d{2})?")


def end_datetime(period: str, year: int, month: int) -> str:
    """'10. 01(목) ~ 11. 12(목) 10:00' + 섹션 연·월 → '2026-11-12 10:00'. 연도는 섹션 제목에서 가져온다."""
    found = _DATE.findall(period or "")
    if not found:
        return ""
    mo, d, tm = found[-1]
    mo, d = int(mo), int(d)
    y = year - 1 if mo - month > 6 else year + 1 if month - mo > 6 else year   # 12월↔1월 경계
    return f"{y}-{mo:02d}-{d:02d}" + (f" {tm}" if tm else "")


def parse_list(md: str) -> list[dict]:
    out, cur, in_month, ym = [], None, False, (0, 0)
    for line in md.splitlines():
        if line.startswith("## "):
            m = _MONTH.match(line)
            in_month = bool(m)   # '지난 행사 기록', '개발자 모임' 등은 건너뛴다
            ym = (2000 + int(m[1]), int(m[2])) if m else ym
            cur = None
            continue
        if not in_month:
            continue
        m = _ITEM.match(line)
        if m:
            cur = {"title": m["title"].strip(), "url": m["url"].strip(), "tags": [], "provider": "",
                   "접수": "", "일시": "", "ym": ym}
            out.append(cur)
            continue
        f = _FIELD.match(line)
        if f and cur is not None:
            key, val = f["key"], f["val"].strip()
            if key == "분류":
                cur["tags"] = re.findall(r"`([^`]+)`", val)
            elif key == "주최":
                cur["provider"] = val
            else:
                cur[key] = val

    items = []
    for e in out:
        period = e["접수"] or e["일시"]
        sched = "".join(f"<li>{k}: {H.escape(e[k])}</li>" for k in ("접수", "일시") if e[k])
        items.append({
            "title": e["title"],
            "provider": e["provider"],
            "category": _category(e["title"]),
            "target": "기타",
            # 원문 기간은 일정 섹션에 그대로 두고, raw_date 는 연도를 붙인 마감 일시로 쓴다 (실패하면 원문)
            "raw_date": end_datetime(period, *e["ym"]) or period,
            "url": e["url"],
            "source_name": "dev_event",
            "keywords": " ".join(e["tags"]),
            "tags": e["tags"],
            "prize_hint": "",
            "_ref": {"source": "dev_event", "id": e["url"]},
            # Dev-Event 는 상세를 따로 가져오지 않으므로 목록의 기간을 일정 섹션으로 쓴다
            "_sections": {"schedule": {"html": f"<ul>{sched}</ul>" if sched else "",
                                       "text": " / ".join(f"{k}: {e[k]}" for k in ("접수", "일시") if e[k])}},
        })
    return items
