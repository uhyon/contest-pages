"""하네스 검증 루프: python evals/run_evals.py

1) 규칙 단위 테스트 (rules.py)
2) offline 전체 그래프 실행 → 기대 결과와 비교 (카카오톡 메시지 + 상세 페이지)
3) 하네스 ON vs OFF(naive_agent) 7개 항목 채점
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["OFFLINE"] = "1"
os.environ["DRY_RUN"] = "1"
os.environ.pop("PAGES_BASE_URL", None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import tempfile  # noqa: E402

from agent import rules, tools  # noqa: E402
from agent.graph import build_graph  # noqa: E402
from evals import naive_agent  # noqa: E402

# 보낸 기록은 실제 data/sent.json 대신 임시 파일을 쓴다
tools.SENT_FILE = Path(tempfile.mkdtemp()) / "sent.json"

S = json.loads((ROOT / "evals" / "eval_samples.json").read_text(encoding="utf-8"))
TODAY = S["today"]
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))


# ------------------------------------------------------------ 1) 규칙 테스트
for c in S["rule_cases"]:
    valid, rejected = rules.validate_items([c["item"]], TODAY)
    visible = bool(valid)
    ok = visible == c["expected_visible"]
    detail = ""
    if visible and ok:
        v = valid[0]
        if "expected_end_date" in c and v["end_date"] != c["expected_end_date"]:
            ok, detail = False, f"end_date {v['end_date']}"
        if "expected_badge" in c and v["badge"] != c["expected_badge"]:
            ok, detail = False, f"badge {v['badge']!r}"
    if not visible and ok and "expected_reason" in c:
        got = rejected[0]["reason"].split(":")[0]
        ok, detail = got == c["expected_reason"], f"reason {got}"
    check(f"{c['id']} {c['desc']}", ok, detail)

for key, cid in (("dedupe_case", "D01"), ("dedupe_url_case", "D02")):
    d = S[key]
    valid, _ = rules.validate_items(d["items"], TODAY)
    check(f"{cid} {d['desc']}", len(valid) == d["expected_valid"], f"valid {len(valid)}")

for g in S["grounded_cases"]:
    got = rules.grounded(g["line"], g["source"])
    check(f"{g['id']} 요약 근거 검사 {g.get('desc', g['line'])}", got == g["expected"], f"got {got}")


# ------------------------------------------------------------ 2) 전체 그래프(하네스 ON)
def run_graph(today: str) -> dict:
    app = build_graph(require_approval=False)
    cfg = {"configurable": {"thread_id": f"eval-{today}"}, "recursion_limit": 30}
    return app.invoke({"interests": ["AI 개발", "데이터 분석", "머신러닝"], "today": today}, cfg)


on = run_graph(TODAY)
exp = S["e2e_expected"]
msgs = on["kakao_messages"]
items = [m for m in msgs if m["_kind"] == "item"]
all_text = "\n".join(m["template"]["text"] for m in msgs)
pages = {v["title"]: (Path(on["pages_dir"]) / v["detail_id"]).read_text(encoding="utf-8") for v in on["valid"]}
index_html = Path(on["preview_path"]).read_text(encoding="utf-8")
links = lambda m: [m["template"]["link"]["web_url"]] + [b["link"]["web_url"] for b in m["template"].get("buttons", [])]

titles = [v["title"] for v in on["valid"]]
check("E01 기대한 공고만 포함", sorted(titles) == sorted(exp["visible_titles"]), str(titles))
check("E02 제외 대상이 카톡·목록 페이지에 없음",
      not any(t in all_text or t in index_html for t in exp["hidden_titles"]))
check("E03 부족 시 재필터 루프 동작", on["attempt"] >= exp["min_attempts"], f"attempt {on['attempt']}")
check("E04 탈락 사유별 집계", rules.reason_counts(on["rejected"]) == exp["rejected_reasons"],
      str(rules.reason_counts(on["rejected"])))
check("E05 리뷰 게이트 PASS", not on["review_errors"], str(on["review_errors"]))
check("E06 DRY_RUN 에서 실제 발송 안 함", on["status"] == "dry_run" and not on["sent"])
check("E07 마감 임박 순 정렬", [v["days_left"] for v in on["valid"]] == sorted(v["days_left"] for v in on["valid"]))
check("E08 카톡 메시지마다 상세 페이지 + 원문 링크",
      all(v["url"] in links(m) and v["detail_url"] in links(m) for m, v in zip(items, on["valid"])) and len(items) == len(on["valid"]))
check("E09 카톡 본문 200자 이하", all(len(m["template"]["text"]) <= rules.KAKAO_TEXT_MAX for m in msgs))
check("E10 카톡에 규칙·일정·상금 한 줄", all(all(k in m["template"]["text"] for k in ("규칙:", "일정:", "상금:")) for m in items))

bad = []
for title, want in exp["summary"].items():
    v = next(x for x in on["valid"] if x["title"] == title)
    bad += [f"{title[:8]}.{k}={v['summary'][k]!r}" for k, w in want.items() if w not in v["summary"][k]]
check("E11 핵심 한 줄이 원문 값과 일치", not bad, str(bad))

order_ok = all(
    0 <= p.find('id="sec-rules"') < p.find('id="sec-schedule"') < p.find('id="sec-prize"') < p.find('id="sec-overview"')
    for p in pages.values())
check("E12 상세 페이지: 규칙·일정·상금이 맨 앞", order_ok)
check("E13 상세 페이지: 우선 3항목은 펼침, 나머지는 접힘",
      all(re.search(r'id="sec-rules" open', p) and not re.search(r'id="sec-overview" open', p) for p in pages.values()))
ni = exp["no_info_section"]
p = pages[ni["title"]]
sec = p[p.find(f'id="sec-{ni["section"]}"'):]
check("E14 원문에 없는 항목은 '정보 없음'", "정보 없음" in sec[:sec.find("</details>")])
check("E15 상세 페이지에 원문 링크·대상·마감일",
      all(not rules.review_page(pages[v["title"]], v) for v in on["valid"]))
check("E16 원문 HTML 정리 (script·data:·javascript: 제거)",
      not any(("<script" in p or "data:image" in p or "javascript:" in p) for p in pages.values()))

empty = run_graph(exp["empty_today"])
check("E17 0건이면 안내 메시지",
      not empty["valid"] and "조건에 맞는 공고가 없습니다" in empty["kakao_messages"][0]["template"]["text"]
      and not empty["review_errors"], str(empty.get("review_errors")))


# ------------------------------------------------------------ 2-1) 새 공고만 보내기
check("N01 첫 실행: 접수 중 공고가 모두 새 공고", len(on["new_items"]) == len(on["valid"]))

seen = on["valid"][:2]
tools.save_sent({rules.sent_key(v): {"title": v["title"]} for v in seen})
again = run_graph(TODAY)
again_items = [m for m in again["kakao_messages"] if m["_kind"] == "item"]
again_text = "\n".join(m["template"]["text"] for m in again_items)
check("N02 이미 보낸 공고는 카톡에서 제외",
      len(again_items) == len(again["valid"]) - 2 and not any(v["title"] in again_text for v in seen)
      and f"새 공고 {len(again_items)}건" in again["kakao_messages"][0]["template"]["text"], again_text[:80])
check("N03 이미 보낸 공고도 상세·목록 페이지에는 남음",
      all(v["title"] in Path(again["preview_path"]).read_text(encoding="utf-8") for v in seen))

tools.save_sent({rules.sent_key(v): {"title": v["title"]} for v in on["valid"]})
none_new = run_graph(TODAY)
check("N04 새 공고가 없으면 안내 1통만 (리뷰 PASS)",
      len(none_new["kakao_messages"]) == 1 and "새 공고가 없습니다" in none_new["kakao_messages"][0]["template"]["text"]
      and not none_new["review_errors"], str(none_new.get("review_errors")))

# 실제 발송 경로(카카오 호출만 가짜로 바꿈): 보낸 공고가 기록되는지
tools.save_sent({})
os.environ["DRY_RUN"], os.environ["PAGES_BASE_URL"] = "0", "https://example.github.io/pages"
_ready, _send = tools.kakao_ready, tools.kakao_send
tools.kakao_ready, tools.kakao_send = (lambda: True), (lambda ts: len(ts))
try:
    real = run_graph(TODAY)
finally:
    os.environ["DRY_RUN"] = "1"
    os.environ.pop("PAGES_BASE_URL", None)
    tools.kakao_ready, tools.kakao_send = _ready, _send
recorded = tools.load_sent()
check("N05 발송하면 보낸 공고를 기록",
      real["status"] == "sent" and set(recorded) == {rules.sent_key(v) for v in real["new_items"]}, str(len(recorded)))
tools.save_sent({})


# ------------------------------------------------------------ 3) ON vs OFF 채점
def score(r: dict) -> dict:
    ms = [m for m in r["kakao_messages"] if m["_kind"] == "item"]
    text = "\n".join(m["template"]["text"] for m in ms)
    urls = [u for m in ms for u in links(m)]
    has = lambda t: t in text
    return {
        "① 마감 공고 제외 (20)": 0 if has("가상 음성 딥러닝") else 20,
        "② 링크 이상 공고 제외 (15)": 15 if all(u.startswith(("http", "file:")) for u in urls) else 0,
        "③ 중복 제거 (15)": 15 if text.count("가상 금융 AI 에이전트 공모전") == 1 else 0,
        "④ 대회 아닌 행사 제외 (10)": 0 if has("가상 AI 밋업") else 10,
        "⑤ 원문+상세 링크 둘 다 (10)": 10 if ms and all(len(set(links(m))) >= 2 for m in ms) else 0,
        "⑥ 부족 시 재필터 (10)": 10 if r["attempt"] >= 2 else 0,
        "⑦ 발송 안전장치 (20)": (10 if not r["review_errors"] else 0) + (10 if r["status"] == "dry_run" else 0),
    }


off = naive_agent.run(TODAY)
s_on, s_off = score(on), score(off)

# ------------------------------------------------------------ 출력
print("\n=== 규칙·그래프 테스트 ===")
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
passed = sum(ok for _, ok, _ in results)
print(f"  → {passed}/{len(results)} PASS")

print("\n=== 하네스 OFF vs ON (100점) ===")
print(f"  {'항목':<26}{'OFF':>6}{'ON':>6}")
for k in s_on:
    print(f"  {k:<24}{s_off[k]:>6}{s_on[k]:>6}")
print(f"  {'합계':<26}{sum(s_off.values()):>6}{sum(s_on.values()):>6}")
print(f"\n  OFF 카톡 공고 수 {len(off['items'])}건(검증 없음) / ON 카톡 공고 수 {len(on['valid'])}건(검증 통과)")

sys.exit(0 if passed == len(results) else 1)
