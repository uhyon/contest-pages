"""카카오톡 '나에게 보내기' 토큰 발급 (처음 한 번만 직접 실행).

python scripts/kakao_login.py

1) 출력된 주소를 브라우저에서 열고 카카오 로그인 + '카카오톡 메시지 전송' 동의
2) 이동한 주소창의 URL 전체(또는 code= 값)를 붙여 넣기
3) data/.kakao_token.json 에 토큰 저장 (화면에는 출력하지 않음)
"""
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from agent import tools  # noqa: E402


def main():
    key = os.getenv("KAKAO_REST_API_KEY")
    redirect = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8080/callback")
    if not key:
        sys.exit(".env 에 KAKAO_REST_API_KEY 를 먼저 넣어 주세요.")
    q = urllib.parse.urlencode({"client_id": key, "redirect_uri": redirect,
                                "response_type": "code", "scope": "talk_message"})
    print("1) 아래 주소를 브라우저에서 열고 로그인·동의하세요:\n")
    print(f"   https://kauth.kakao.com/oauth/authorize?{q}\n")
    print(f"2) '{redirect}?code=...' 로 이동하면(페이지가 안 열려도 괜찮습니다) 주소창의 URL 전체를 붙여 넣으세요.")
    raw = input("> ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [raw])[0]

    data = {"grant_type": "authorization_code", "client_id": key, "redirect_uri": redirect, "code": code}
    if os.getenv("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    res = tools._post_form(tools.KAUTH, data)
    if "refresh_token" not in res:
        sys.exit(f"토큰 발급 실패: {res.get('error')} {res.get('error_description')}")
    tools.write_text(tools.TOKEN_FILE, json.dumps({"access_token": res["access_token"],
                                                   "refresh_token": res["refresh_token"]}))
    print(f"\n완료: {tools.TOKEN_FILE} 에 저장했습니다. 이제 python main.py 로 실행하세요.")


if __name__ == "__main__":
    main()
