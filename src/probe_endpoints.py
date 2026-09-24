"""
V2 端点验证探针（第二批）：homefeed(POST) / following list(www host) / follow feed 变体。
"""
import os, json, time, random
from curl_cffi import requests as cffi
from xhshow import Xhshow, SessionManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(ROOT, "secrets", "cookies.json")
HOME = "https://www.xiaohongshu.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")
xs = Xhshow()
sm_global = SessionManager()

def load_cookies():
    with open(COOKIE_FILE, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if v}

def get_session(cookies):
    s = cffi.Session(impersonate="chrome131")
    r0 = s.get(HOME, headers={"User-Agent": UA}, timeout=20)
    a1 = cookies.get("a1", "")
    ck = {"web_session": cookies.get("web_session", ""), "a1": a1}
    try:
        webid = xs.generate_web_id(a1)
        if webid: ck["webId"] = webid
    except Exception: pass
    try:
        acw = r0.cookies.get("acw_tc")
        if acw: ck["acw_tc"] = acw
    except Exception: pass
    s.cookies.clear()
    return s, ck

def signed_get(s, host, path, params, ck):
    url = f"{host}/api/sns/web/{path}"
    sign = xs.sign_headers_get(url, dict(ck), params=params, session=sm_global)
    r = s.get(url, params=params, headers={"User-Agent": UA, "Referer": HOME, **sign},
              cookies=ck, timeout=20)
    try:
        acw = r.cookies.get("acw_tc")
        if acw: ck["acw_tc"] = acw
    except Exception: pass
    s.cookies.clear()
    return r

def signed_post(s, host, path, payload, ck):
    url = f"{host}/api/sns/web/{path}"
    sign = xs.sign_headers_post(url, dict(ck), payload=payload, session=sm_global)
    r = s.post(url, json=payload, headers={"User-Agent": UA, "Referer": HOME,
                 "Content-Type": "application/json", **sign}, cookies=ck, timeout=20)
    try:
        acw = r.cookies.get("acw_tc")
        if acw: ck["acw_tc"] = acw
    except Exception: pass
    s.cookies.clear()
    return r

def show(name, r):
    try:
        j = r.json()
    except Exception:
        print(f"  [{name}] 非JSON status={r.status_code} body={r.text[:150]}"); return None
    code = j.get("code")
    data = j.get("data") or {}
    lists = {k: (len(v) if isinstance(v, list) else '?') for k, v in data.items() if isinstance(v, list)}
    print(f"  [{name}] code={code} msg={j.get('msg')} lists={lists} has_more={data.get('has_more')}")
    return j

def main():
    cookies = load_cookies()
    uid = cookies.get("user_id", "")
    s, ck = get_session(cookies)
    print(f"[*] user_id={uid}")

    print("\n=== A. HOMEFEED recommend (POST edith) ===")
    payload = {"num": 20, "cursor_score": "", "refresh_type": 1, "note_index": 0,
               "unread_begin_note_id": "", "unread_end_note_id": "", "unread_note_count": 0,
               "search_page_request_source": "discover_feed"}
    show("homefeed_recommend", signed_post(s, "https://edith.xiaohongshu.com", "v1/homefeed", payload, ck))

    print("\n=== B. HOMEFEED follow (POST edith, src=following) ===")
    p2 = dict(payload); p2["search_page_request_source"] = "following"
    show("homefeed_following", signed_post(s, "https://edith.xiaohongshu.com", "v1/homefeed", p2, ck))

    print("\n=== C. FOLLOWING LIST (GET www host, uid in path) ===")
    show("following_list_www", signed_get(s, "https://www.xiaohongshu.com",
         f"v1/user/{uid}/following", {"page": 1, "page_size": 20}, ck))

    print("\n=== D. FOLLOW FEED variant (GET edith followfeed) ===")
    show("followfeed_get", signed_get(s, "https://edith.xiaohongshu.com", "v1/followfeed",
         {"num": 20, "cursor_score": "", "image_formats": "webp"}, ck))

if __name__ == "__main__":
    main()
