"""원문 공고의 HTML 섹션을 상세 페이지에 넣을 수 있게 정리한다.

- 허용한 태그만 남기고 style/class/스크립트는 버린다.
- 링크·이미지는 http(s) 절대경로만 남긴다 (data: URI, javascript: 차단).
- 내용은 바꾸지 않는다: 원문 문장을 그대로 보여 주는 것이 '추측 금지' 규칙을 지키는 가장 쉬운 방법이다.
"""
from __future__ import annotations

import html as H
import re
from html.parser import HTMLParser

_KEEP = {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u", "table", "thead", "tbody",
         "tr", "td", "th", "a", "img", "h2", "h3", "h4", "blockquote", "hr", "code", "pre"}
_HEADING = {"h1": "h3", "h2": "h3", "h3": "h4", "h4": "h4", "h5": "h4", "h6": "h4"}
_DROP_CONTENT = {"script", "style", "iframe", "noscript"}
_VOID = {"br", "img", "hr"}


class _Cleaner(HTMLParser):
    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.base = base_url.rstrip("/")

    def _abs(self, url: str) -> str:
        url = (url or "").strip()
        if url.startswith("/") and self.base:
            url = self.base + url
        return url if re.match(r"^https?://", url) else ""

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_CONTENT:
            self.skip += 1
            return
        if self.skip:
            return
        tag = _HEADING.get(tag, tag)
        if tag not in _KEEP:
            return
        a = dict(attrs)
        if tag == "a":
            href = self._abs(a.get("href", ""))
            self.out.append(f'<a href="{H.escape(href)}" target="_blank" rel="noopener">' if href else "<a>")
        elif tag == "img":
            src = self._abs(a.get("src", ""))
            if src:
                self.out.append(f'<img src="{H.escape(src)}" alt="" loading="lazy">')
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in _DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        tag = _HEADING.get(tag, tag)
        if tag in _KEEP and tag not in _VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(H.escape(data))


def clean_html(raw: str | None, base_url: str = "") -> str:
    """원문 HTML → 안전한 HTML. 내용이 비어 있으면 빈 문자열."""
    if not raw or not str(raw).strip():
        return ""
    c = _Cleaner(base_url)
    c.feed(str(raw))
    c.close()
    out = "".join(c.out)
    out = re.sub(r"<p>\s*</p>|<(strong|b|em|i|u)>\s*</\1>", "", out)
    return out.strip() if to_text(out) else ""


def to_text(raw: str | None) -> str:
    """HTML → 공백 하나로 정리한 평문 (요약·근거 검사용)."""
    if not raw:
        return ""
    t = re.sub(r"<br\s*/?>|</(p|li|tr|h\d)>", "\n", str(raw))
    t = H.unescape(re.sub(r"<[^>]+>", " ", t)).replace("﻿", "").replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()
