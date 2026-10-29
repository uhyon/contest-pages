"""실행 진입점.

python main.py --offline      # 키·네트워크 없이 가상 데이터로 전체 흐름 실습
python main.py                # 실제 사이트 수집 + 상세 페이지·카카오 미리보기 (DRY_RUN=1 이면 발송 안 함)
python main.py --auto-send    # 승인 질문 없이 발송 (스케줄 실행용)
"""
import argparse
import os
import sys
import uuid
from datetime import date

from langgraph.errors import GraphRecursionError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if hasattr(sys.stdout, "reconfigure"):   # Windows 콘솔에서 한글·이모지 깨짐 방지
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--interests", default=os.getenv("INTERESTS", "AI 개발,데이터 분석,머신러닝"),
                   help="쉼표로 구분한 관심 분야")
    p.add_argument("--today", default=os.getenv("TODAY", date.today().isoformat()))
    p.add_argument("--offline", action="store_true")
    p.add_argument("--auto-send", action="store_true")
    a = p.parse_args()
    if a.offline:
        os.environ["OFFLINE"] = "1"

    from agent.graph import build_graph  # 환경 변수 설정 후 import
    app = build_graph(require_approval=not a.auto_send)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 30}
    init = {"interests": [s.strip() for s in a.interests.split(",") if s.strip()], "today": a.today}

    def run(inp):
        for step in app.stream(inp, config, stream_mode="updates"):
            for upd in step.values():
                for line in (upd or {}).get("log", []):
                    print(line)

    try:
        run(init)
    except GraphRecursionError:
        print("[error] recursion_limit 도달 — 재필터 루프를 확인하세요.")
        return

    snap = app.get_state(config)
    if snap.next == ("publish",):  # interrupt 로 멈춘 상태
        v = snap.values
        print(f"\n카카오톡 메시지 {len(v['kakao_messages'])}개 · 목록 페이지: {v['preview_path']}")
        try:
            answer = input("카카오톡으로 보낼까요? (y/N) ")
        except EOFError:   # 입력이 없는 환경(스케줄러 등)에서는 보내지 않는다
            answer = ""
        if answer.strip().lower() == "y":
            run(None)  # 멈춘 지점부터 재개
        else:
            print("발송을 취소했습니다.")

    final = app.get_state(config).values
    from agent import rules
    print(f"\n결과: status={final.get('status', 'cancelled')}, valid={len(final.get('valid', []))}, "
          f"rejected={len(final.get('rejected', []))} {rules.reason_counts(final.get('rejected', []))}")


if __name__ == "__main__":
    main()
