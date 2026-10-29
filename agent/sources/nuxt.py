"""DACON 페이지에 박혀 있는 window.__NUXT__=(function(a,b,..){return {...}}(인자들)) 를
JS 엔진 없이 파이썬 객체로 바꾼다. (DACON 은 공개 JSON API 가 없어서 SSR 데이터를 읽는다)

지원 범위: 객체·배열·문자열·숫자·true/false/null/void 0·인자 변수. 그 밖의 표현식은 None.
"""
from __future__ import annotations

import json
import re

_TOKEN = re.compile(r'''
    (?P<str>"(?:\\.|[^"\\])*")
  | (?P<num>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<void>void\s+0)
  | (?P<id>[A-Za-z_$][\w$]*)
  | (?P<punc>[{}\[\]:,()])
  | (?P<ws>\s+)
  | (?P<other>.)
''', re.X | re.S)


class _Ref(str):
    """함수 인자 이름(나중에 실제 값으로 바꾼다)."""


def _tokens(src: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group()) for m in _TOKEN.finditer(src) if m.lastgroup != "ws"]


def _js_str(s: str) -> str:
    try:
        return json.loads(s, strict=False)
    except json.JSONDecodeError:   # JSON 에 없는 \x.. 같은 이스케이프
        return re.sub(r"\\(.)", r"\1", s[1:-1])


def _resolve(o, env: dict):
    if isinstance(o, _Ref):
        return env.get(str(o))
    if isinstance(o, dict):
        return {k: _resolve(v, env) for k, v in o.items()}
    if isinstance(o, list):
        return [_resolve(v, env) for v in o]
    return o


class _Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("eof", "")

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def value(self):
        kind, v = self.take()
        if kind == "str":
            return _js_str(v)
        if kind == "num":
            return float(v) if any(c in v for c in ".eE") else int(v)
        if kind == "void":
            return None
        if kind == "id":
            lit = {"true": True, "false": False, "null": None, "undefined": None}
            if v in lit:
                return lit[v]
            if self.peek() == ("punc", "("):   # Array(3) 같은 호출은 값 없이 건너뛴다
                self.skip_group("(", ")")
                return None
            return _Ref(v)
        if v == "{":
            return self.obj()
        if v == "[":
            return self.arr()
        return None

    def skip_group(self, open_, close):
        depth = 0
        while self.peek()[0] != "eof":
            _, v = self.take()
            depth += (v == open_) - (v == close)
            if depth == 0:
                return

    def obj(self):
        out = {}
        while self.peek() != ("punc", "}") and self.peek()[0] != "eof":
            kind, k = self.take()
            key = _js_str(k) if kind == "str" else k
            self.take()  # ':'
            out[key] = self.value()
            if self.peek() == ("punc", ","):
                self.take()
        self.take()
        return out

    def arr(self):
        out = []
        while self.peek() != ("punc", "]") and self.peek()[0] != "eof":
            out.append(self.value())
            if self.peek() == ("punc", ","):
                self.take()
        self.take()
        return out


def parse_nuxt(html: str) -> dict:
    """페이지 HTML → __NUXT__ 객체. 못 찾으면 {}."""
    m = re.search(r"window\.__NUXT__=\(function\(([^)]*)\)\{return ", html)
    if not m:
        return {}
    params = [x.strip() for x in m.group(1).split(",") if x.strip()]
    p = _Parser(_tokens(html[m.end():html.find("</script>", m.end())]))
    body = p.value()
    p.take(), p.take()   # '}' '('
    args = []
    while p.peek()[0] != "eof" and p.peek() != ("punc", ")"):
        args.append(p.value())
        if p.peek() == ("punc", ","):
            p.take()
    return _resolve(body, dict(zip(params, args))) or {}
