"""V2 结构探测：dump search / homefeed(recommend+following) 单条 item 关键字段，确认解析路径。"""
import os, json, time
from curl_cffi import requests as cffi
from xhshow import Xhshow, SessionManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(ROOT, "secrets", "cookies.json")
HOME = "https://www.xiaohongshu.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")
xs = Xhshow(); sm = SessionManager()

def load_cookies():
    with open(COOKIE_FILE, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if v}

def get_session(cookies):
    s = cffi.Session(impersonate="chrome131")
    r0 = s.get(HOME, headers={"User-Agent": UA}, timeout=20)
    a1 = cookies.get("a1", ""); ck = {"web_session": cookies.get("web_session",""), "a1": a1}
    try:
        w = xs.generate_web_id(a1)
        if w: ck["webId"] = w
    except Exception: pass
    try:
        acw = r0.cookies.get("acw_tc")
        if acw: ck["acw_tc"] = acw
    except Exception: pass
    s.cookies.clear(); return s, ck

def sget(s, host, path, params, ck):
    url = f"{host}/api/sns/web/{path}"
    sign = xs.sign_headers_get(url, dict(ck), params=params, session=sm)
    r = s.get(url, params=params, headers={"User-Agent":UA,"Referer":HOME,**sign}, cookies=ck, timeout=20)
    try:
        acw=r.cookies.get("acw_tc")
        if acw: ck["acw_tc"]=acw
    except Exception: pass
    s.cookies.clear(); return r

def spost(s, host, path, payload, ck):
    url = f"{host}/api/sns/web/{path}"
    sign = xs.sign_headers_post(url, dict(ck), payload=payload, session=sm)
    r = s.post(url, json=payload, headers={"User-Agent":UA,"Referer":HOME,"Content-Type":"application/json",**sign}, cookies=ck, timeout=20)
    try:
        acw=r.cookies.get("acw_tc")
        if acw: ck["acw_tc"]=acw
    except Exception: pass
    s.cookies.clear(); return r

def dump(name, items):
    if not items:
        print(f"  [{name}] 无 items"); return
    it = items[0]
    nc = it.get("note_card") or it
    print(f"  [{name}] 顶层keys={sorted(it.keys())}")
    print(f"    note_card keys={sorted(nc.keys())}")
    print(f"    note_id={nc.get('note_id')} type={nc.get('type')} title={nc.get('display_title') or nc.get('title')}")
    print(f"    user={nc.get('user',{}).get('nickname')} xsec={(nc.get('xsec_token') or '')[:20]}...")
    print(f"    has video={('video' in nc)} has image_list={('image_list' in nc)} cover={'cover' in nc}")

def main():
    cookies = load_cookies(); uid = cookies.get("user_id","")
    s, ck = get_session(cookies)
    # search
    sid = "v2_"+str(int(time.time()*1000))
    r = spost(s, "https://edith.xiaohongshu.com", "v1/search/notes",
              {"keyword":"Obsidian","page":1,"page_size":20,"search_id":sid,"sort":"general","note_type":0,"ext_flags":[],"image_formats":["jpg","webp","avif"]}, ck)
    j=r.json(); dump("search", j.get("data",{}).get("items",[]))
    # homefeed recommend
    r = spost(s, "https://edith.xiaohongshu.com", "v1/homefeed",
              {"num":20,"cursor_score":"","refresh_type":1,"note_index":0,"unread_begin_note_id":"","unread_end_note_id":"","unread_note_count":0,"search_page_request_source":"discover_feed"}, ck)
    j=r.json(); dump("homefeed_recommend", j.get("data",{}).get("items",[]))
    # homefeed following
    r = spost(s, "https://edith.xiaohongshu.com", "v1/homefeed",
              {"num":20,"cursor_score":"","refresh_type":1,"note_index":0,"unread_begin_note_id":"","unread_end_note_id":"","unread_note_count":0,"search_page_request_source":"following"}, ck)
    j=r.json(); dump("homefeed_following", j.get("data",{}).get("items",[]))
    # following list retry (edith, uid in path)
    print("\n=== retry following list ===")
    for path in [f"v1/user/{uid}/following", f"v1/user/following?user_id={uid}&num=30&cursor="]:
        r = sget(s, "https://edith.xiaohongshu.com", path, {}, ck) if "?" not in path else sget(s, "https://edith.xiaohongshu.com", path.split("?")[0], dict([p.split("=") for p in path.split("?")[1].split("&")]), ck)
        try: print(f"  [{path[:40]}] code={r.json().get('code')} msg={r.json().get('msg')}")
        except Exception: print(f"  [{path[:40]}] status={r.status_code} body={r.text[:120]}")

if __name__ == "__main__":
    main()
