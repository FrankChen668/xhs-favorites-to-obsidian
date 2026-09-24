"""
Phase 0 探针（最终版）：验证 curl_cffi + xhshow 能拉到一页收藏。
- 修复：web_session/a1 必须真正写进请求 Cookie（指定 domain），
- 收藏接口必须带 user_id。
- 只读一页，不下载、不动收藏。成功则打印 note_type 分布。
"""
import json
from curl_cffi import requests as cffi
from xhshow import Xhshow, SessionManager

COOKIE_FILE = "secrets/cookies.json"
HOME = "https://www.xiaohongshu.com/"
COLLECT = "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")

xs = Xhshow()


def load_cookies():
    with open(COOKIE_FILE, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if v}


def main():
    cookies = load_cookies()
    user_id = cookies.get("user_id", "")
    s = cffi.Session(impersonate="chrome131")
    r0 = s.get(HOME, headers={"User-Agent": UA}, timeout=20)
    print("[home] status=", r0.status_code)

    a1 = cookies.get("a1", "")
    if "webId" not in s.cookies and a1:
        try:
            s.cookies.set("webId", xs.generate_web_id(a1))
        except Exception as e:
            print("generate_web_id 失败(可忽略):", e)
    # 关键：把 web_session/a1 真正写入会话 Cookie，随请求发出
    for k, v in cookies.items():
        if k in ("web_session", "a1"):
            s.cookies.set(k, v, domain=".xiaohongshu.com")

    cd = dict(s.cookies)
    sm = SessionManager()
    params = {"num": 30, "cursor": "", "image_formats": "webp", "user_id": user_id}
    sign = xs.sign_headers_get(COLLECT, cd, params=params, session=sm)
    r = s.get(COLLECT, params=params,
              headers={"User-Agent": UA, "Referer": HOME, **sign}, timeout=20)
    print("[collect] http=", r.status_code)
    try:
        j = r.json()
    except Exception:
        print("非 JSON 返回：", r.text[:500])
        return
    print("[collect] code=", j.get("code"), "msg=", j.get("msg"))
    data = j.get("data") or {}
    items = data.get("notes") or data.get("items") or data.get("cards") or []
    print("本页条目数:", len(items))
    # type: "normal"=图文, "video"=视频（不同版本字段可能不同）
    from collections import Counter
    types = Counter()
    samples = []
    for it in items:
        note = it.get("note_card") or it.get("note") or it
        nt = note.get("type") or note.get("note_type") or ("video" if note.get("video") else "normal")
        types[str(nt)] += 1
        if len(samples) < 5:
            samples.append(note.get("display_title") or note.get("title") or "(无标题)")
    print("type 分布:", dict(types))
    for i, t in enumerate(samples):
        print(f"  样例{i+1}: {t}")
    has_more = data.get("has_more")
    cursor = data.get("cursor")
    print("has_more=", has_more, " next_cursor=", cursor)


if __name__ == "__main__":
    main()
