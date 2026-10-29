"""외부 연동(사이트 수집·LLM·카카오톡·파일 저장). 키가 없으면 자동으로 offline / dry-run 으로 바뀐다.

환경 제약(하네스): 이 파일만 외부와 통신한다. 노드는 여기 함수만 호출한다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .sources import dacon, daker, dev_event

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures"
TOKEN_FILE = ROOT / "data" / ".kakao_token.json"   # .gitignore 대상
UA = "Mozilla/5.0 (contest-alert-agent; personal use)"
ALL_SOURCES = ("dacon", "daker", "dev_event")


def is_offline() -> bool:
    return os.getenv("OFFLINE", "0") == "1"


def enabled_sources() -> list[str]:
    raw = os.getenv("SOURCES", ",".join(ALL_SOURCES))
    return [s.strip() for s in raw.split(",") if s.strip() in ALL_SOURCES]


# ---------------------------------------------------------------- HTTP
def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
    time.sleep(float(os.getenv("FETCH_DELAY", "0.5")))   # 사이트에 부담 주지 않게
    return body


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 수집
def fetch_listing(source: str) -> list[dict]:
    """사이트 목록 → 표준 스키마 후보 목록."""
    if source == "dacon":
        raw = _fixture("dacon_list.html") if is_offline() else http_get(dacon.LIST_URL)
        return dacon.parse_list(raw)
    if source == "daker":
        raw = _fixture("daker_list.json") if is_offline() else http_get(daker.LIST_URL)
        return daker.parse_list(json.loads(raw))
    if source == "dev_event":
        raw = _fixture("dev_event.md") if is_offline() else http_get(dev_event.LIST_URL)
        return dev_event.parse_list(raw)
    raise ValueError(f"unknown source {source}")


def fetch_detail(ref: dict) -> dict:
    """상세 원문 → {"sections": {...}, "facts": {...}}. 상세가 없는 소스는 빈 값."""
    src, rid = ref.get("source"), ref.get("id")
    if src == "dacon":
        raw = _fixture(f"dacon_detail_{rid}.html") if is_offline() else http_get(dacon.detail_url(rid))
        return dacon.parse_detail(raw)
    if src == "daker":
        raw = _fixture(f"daker_detail_{rid}.json") if is_offline() else http_get(daker.detail_api(rid))
        return daker.parse_detail(json.loads(raw))
    return {"sections": {}, "facts": {}}


# ---------------------------------------------------------------- LLM
def get_llm():
    """LLM_PROVIDER=gemini | openai | none. none 이거나 키가 없으면 None (규칙 기반으로 대체)."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "none" or is_offline():
        return None
    if provider == "gemini" and os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=os.getenv("LLM_MODEL", "gemini-2.5-flash"), temperature=0)
    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o-mini"), temperature=0)
    return None


# ---------------------------------------------------------------- 파일
def secret_values() -> list[str]:
    keys = ("GOOGLE_API_KEY", "OPENAI_API_KEY", "KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET",
            "KAKAO_REFRESH_TOKEN")
    vals = [os.getenv(k, "") for k in keys]
    if TOKEN_FILE.exists():
        tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        vals += [tok.get("access_token", ""), tok.get("refresh_token", "")]
    return vals


def pages_dir(today: str) -> Path:
    """상세 페이지 저장 위치: PAGES_DIR/YYYY-MM-DD/ (기본 outbox/pages, GitHub Actions 에서는 docs).
    PAGES_DIR 를 웹에 올리면 PAGES_BASE_URL 로 열린다."""
    d = ROOT / os.getenv("PAGES_DIR", "outbox/pages") / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def page_url(today: str, filename: str) -> str:
    """PAGES_BASE_URL 이 있으면 공개 주소, 없으면 로컬 파일 주소(미리보기용)."""
    base = os.getenv("PAGES_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/{today}/{urllib.parse.quote(filename)}"
    return (pages_dir(today) / filename).as_uri()


def write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------- 보낸 공고 기록
SENT_FILE = ROOT / "data" / "sent.json"   # {url키: {title, end_date, sent_at}} — Actions 가 저장소에 커밋한다


def load_sent() -> dict:
    return json.loads(SENT_FILE.read_text(encoding="utf-8")) if SENT_FILE.exists() else {}


def save_sent(sent: dict) -> None:
    write_text(SENT_FILE, json.dumps(sent, ensure_ascii=False, indent=1, sort_keys=True))


# ---------------------------------------------------------------- 상세 페이지 공개 (git push)
def publish_enabled() -> bool:
    return os.getenv("PAGES_PUBLISH", "") == "git"


def publish_pages(today: str, wait_url: str, timeout: int = 300) -> str:
    """PAGES_DIR 를 커밋·푸시하고, GitHub Pages 에 반영될 때까지(wait_url 이 200) 기다린다."""
    import subprocess

    run = lambda *a: subprocess.run(a, cwd=ROOT, check=True, capture_output=True, text=True)
    run("git", "add", os.getenv("PAGES_DIR", "outbox/pages"))
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        run("git", "commit", "-m", f"pages: {today}")
        run("git", "push")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{wait_url}?t={int(time.time())}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return "ok"
        except Exception:
            pass
        time.sleep(15)
    return "timeout"


# ---------------------------------------------------------------- 카카오톡 (나에게 보내기)
KAUTH = "https://kauth.kakao.com/oauth/token"
MEMO_API = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _post_form(url: str, data: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def kakao_ready() -> bool:
    return bool(os.getenv("KAKAO_REST_API_KEY")) and (TOKEN_FILE.exists() or bool(os.getenv("KAKAO_REFRESH_TOKEN")))


def kakao_access_token() -> str:
    """refresh_token 으로 access_token 을 새로 받는다. 새 refresh_token 이 오면 저장한다."""
    tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8")) if TOKEN_FILE.exists() else {}
    refresh = tok.get("refresh_token") or os.environ["KAKAO_REFRESH_TOKEN"]
    data = {"grant_type": "refresh_token", "client_id": os.environ["KAKAO_REST_API_KEY"], "refresh_token": refresh}
    if os.getenv("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    res = _post_form(KAUTH, data)
    tok["access_token"] = res["access_token"]
    if res.get("refresh_token"):
        tok["refresh_token"] = res["refresh_token"]
    write_text(TOKEN_FILE, json.dumps(tok))
    return tok["access_token"]


def kakao_send(templates: list[dict]) -> int:
    """카카오톡 '나에게 보내기'. 보낸 개수를 돌려준다."""
    token = kakao_access_token()
    for t in templates:
        res = _post_form(MEMO_API, {"template_object": json.dumps(t, ensure_ascii=False)}, token)
        if res.get("result_code") != 0:
            raise RuntimeError(f"카카오 발송 실패: {res}")
    return len(templates)
