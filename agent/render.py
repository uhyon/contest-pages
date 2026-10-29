"""코드가 조립하는 출력물: 상세 페이지 HTML · 목록 페이지 HTML · 카카오톡 템플릿.

링크·날짜·기관명·섹션 본문은 모두 검증된 데이터에서 그대로 가져온다 (LLM 이 쓰지 않는다).
"""
from __future__ import annotations

import html as H
import re

from . import rules
from .sources import PRIORITY_KEYS, SECTION_KEYS, SECTION_LABELS

ICON = {"rules": "📌", "schedule": "🗓", "prize": "💰"}
E = H.escape

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b1f24;--sub:#5b6573;--line:#e3e6ea;--accent:#2563eb;
--accent-bg:#eef4ff;--hot:#d9480f;--hot-bg:#fff1e8;--muted:#8a94a3}
@media (prefers-color-scheme: dark){:root{--bg:#111418;--card:#1a1f25;--ink:#e8ebef;--sub:#a5afbb;
--line:#2c333b;--accent:#6ea0ff;--accent-bg:#1b2840;--hot:#ff8a50;--hot-bg:#3a2316;--muted:#77818d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:16px}
header{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
h1{font-size:21px;line-height:1.35;margin:6px 0 8px}
.meta{color:var(--sub);font-size:14px}.meta b{color:var(--ink);font-weight:600}
.badge{display:inline-block;font-size:13px;font-weight:700;border-radius:999px;padding:2px 10px;
background:var(--hot-bg);color:var(--hot)}
.dday{background:var(--accent-bg);color:var(--accent)}
.btn{display:block;text-align:center;margin-top:14px;padding:12px;border-radius:10px;
background:var(--accent);color:#fff;font-weight:700;text-decoration:none}
h2.group{font-size:15px;color:var(--sub);margin:22px 4px 8px;font-weight:700}
.sec{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:10px 0;overflow:hidden}
.sec.key{border:2px solid var(--accent)}
.sec>summary{list-style:none;cursor:pointer;padding:14px 16px;display:flex;gap:8px;align-items:baseline}
.sec>summary::-webkit-details-marker{display:none}
.sec.key>summary{background:var(--accent-bg)}
.sec h3.t{margin:0;font-size:18px}.sec.sub h3.t{font-size:16px;font-weight:600}
.one{display:block;font-weight:700;color:var(--accent);font-size:15px;margin-top:2px}
.body{padding:4px 16px 16px;font-size:15px;overflow-x:auto}
.body img{max-width:100%;height:auto}.body table{border-collapse:collapse;margin:8px 0}
.body td,.body th{border:1px solid var(--line);padding:4px 8px;font-size:14px}
.none{color:var(--muted);padding:4px 16px 16px;font-size:14px}
.chev{margin-left:auto;color:var(--muted);font-size:13px}
.key3{background:var(--card);border:2px solid var(--accent);border-radius:14px;margin-top:10px;overflow:hidden}
.key3 a{display:flex;flex-direction:column;padding:10px 16px;text-decoration:none;color:inherit;
border-top:1px solid var(--line)}.key3 a:first-child{border-top:0}
.key3 span{font-size:13px;color:var(--sub)}.key3 b{font-size:16px;color:var(--ink)}
footer{color:var(--muted);font-size:13px;margin:20px 4px 40px}
.item{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;
margin:10px 0;color:inherit;text-decoration:none}
"""


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{E(title)}</title><style>{_CSS}</style></head>"
            f'<body><div class="wrap">{body}</div></body></html>')


def dday(v: dict) -> str:
    return "D-DAY" if v.get("days_left") == 0 else f"D-{v.get('days_left')}"


def target_label(v: dict) -> str:
    t = v.get("target") or "기타"
    return rules.NO_INFO if t == "기타" else t


def _meta(v: dict) -> str:
    """'주최 · 분류 · 대상 X' (분류가 '기타'면 생략)"""
    cat = v.get("category", "")
    return " · ".join([v["provider"]] + ([cat] if cat and cat != "기타" else []) + [f"대상 {target_label(v)}"])


def _section(key: str, v: dict, priority: bool) -> str:
    sec = (v.get("sections") or {}).get(key) or {}
    one = (v.get("summary") or {}).get(key, "") if priority else ""
    head = (f'<h3 class="t">{ICON.get(key, "")} {E(SECTION_LABELS[key])}</h3>'
            + (f'<span class="one">{E(one)}</span>' if one and one != rules.NO_INFO else ""))
    body = (f'<div class="body">{sec["html"]}</div>' if sec.get("html")
            else f'<p class="none">{rules.NO_INFO} — 원문 공고에서 이 항목을 찾지 못했습니다. 원문을 확인하세요.</p>')
    cls = "key" if priority else "sub"
    # 우선 3항목은 펼친 채로, 나머지는 접어서 보여 준다
    return (f'<details class="sec {cls}" id="sec-{key}"{" open" if priority else ""}>'
            f'<summary><div>{head}</div><span class="chev">{"접기" if priority else "펼치기"}</span></summary>'
            f"{body}</details>")


def detail_page(v: dict) -> str:
    badge = f'<span class="badge">{E(v["badge"])}</span> ' if v.get("badge") else ""
    header = (
        f'<header>{badge}<span class="badge dday">{dday(v)}</span>'
        f'<h1>{E(v["title"])}</h1>'
        f'<div class="meta">{E(_meta(v))}</div>'
        f'<div class="meta">마감 <b>{E(rules.deadline_of(v))}</b> ({v["end_date"]}) · 출처 {E(v.get("source_name", ""))}</div>'
        f'<a class="btn" href="{E(v["url"])}" target="_blank" rel="noopener">원문 공고 바로가기 →</a></header>')
    s = v.get("summary") or {}
    header += '<nav class="key3">' + "".join(
        f'<a href="#sec-{k}"><span>{ICON[k]} {E(SECTION_LABELS[k])}</span><b>{E(s.get(k, rules.NO_INFO))}</b></a>'
        for k in PRIORITY_KEYS) + "</nav>"
    first = "".join(_section(k, v, True) for k in PRIORITY_KEYS)
    rest = "".join(_section(k, v, False) for k in SECTION_KEYS if k not in PRIORITY_KEYS)
    body = (header + '<h2 class="group">먼저 볼 3가지</h2>' + first
            + '<h2 class="group">더 보기</h2>' + rest
            + f'<footer>자동 수집 결과입니다. 신청 전 <a href="{E(v["url"])}" target="_blank" rel="noopener">원문 공고</a>를 꼭 확인하세요.</footer>')
    return _page(v["title"], body)


def index_page(valid: list[dict], today: str) -> str:
    if not valid:
        return _page("AI 공모전 알림", f"<h1>AI 공모전 알림 · {today}</h1><p>이번에는 조건에 맞는 공고가 없습니다.</p>")
    rows = "".join(
        f'<a class="item" href="{E(v["detail_url"])}">'
        + (f'<span class="badge">{E(v["badge"])}</span> ' if v.get("badge") else "")
        + f'<span class="badge dday">{dday(v)}</span><br><b>{E(v["title"])}</b>'
        f'<div class="meta">{E(_meta(v))} · 마감 {v["end_date"]}</div></a>'
        for v in valid)
    return _page("AI 공모전 알림", f"<h1>AI 공모전 알림 · {today}</h1><p class='meta'>마감 임박 순 {len(valid)}건</p>{rows}")


# ---------------------------------------------------------------- 카카오톡 텍스트 템플릿
def _link(url: str) -> dict:
    return {"web_url": url, "mobile_web_url": url}


def _fit(lines: list[str], limit: int) -> str:
    """200자 제한: 넘으면 제목 줄(2번째 줄)을 줄인다."""
    text = "\n".join(lines)
    over = len(text) - limit
    if over > 0:
        lines[1] = lines[1][: max(8, len(lines[1]) - over - 1)] + "…"
        text = "\n".join(lines)
    return text[:limit]


def kakao_item(v: dict) -> dict:
    s = v.get("summary") or {}
    tag = f"{v['badge']} · {dday(v)}" if v.get("badge") else dday(v)
    lines = [f"[{tag}]",
             v["title"],
             _meta(v),
             f"{ICON['rules']} 규칙: {s.get('rules', rules.NO_INFO)}",
             f"{ICON['schedule']} 일정: {s.get('schedule', rules.NO_INFO)}",
             f"{ICON['prize']} 상금: {s.get('prize', rules.NO_INFO)}"]
    detail = v.get("detail_url") or v["url"]
    return {"object_type": "text", "text": _fit(lines, rules.KAKAO_TEXT_MAX), "link": _link(detail),
            "buttons": [{"title": "상세 보기", "link": _link(detail)},
                        {"title": "원문 공고", "link": _link(v["url"])}]}


def kakao_header(valid: list[dict], new: list[dict], shown: int, today: str, index_url: str) -> dict:
    if not valid:
        text = f"[AI 공모전 알림] {today}\n이번에는 조건에 맞는 공고가 없습니다.\n다음 알림에서 다시 확인해 드릴게요."
    elif not new:
        text = (f"[AI 공모전 알림] {today}\n지난 알림 이후 새 공고가 없습니다.\n"
                f"접수 중인 공고 {len(valid)}건은 전체 목록에서 볼 수 있어요.")
    else:
        text = f"[AI 공모전 알림] {today} · 새 공고 {len(new)}건\n마감 임박 순으로 보내 드려요. (접수 중 전체 {len(valid)}건)"
        if len(new) > shown:
            text += f"\n새 공고 중 {shown}건만 먼저 보내고, 나머지 {len(new) - shown}건은 다음 알림에서 보내요."
    return {"object_type": "text", "text": text, "link": _link(index_url), "button_title": "전체 목록"}


def slug(v: dict) -> str:
    ref = v.get("_ref") or {}
    base = f"{ref.get('source', v.get('source_name', 'x'))}-{ref.get('id', v['title'])}"
    return re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", str(base))[:80].strip("-") + ".html"
