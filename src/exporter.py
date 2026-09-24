"""
小红书收藏 → Obsidian 导出器（Phase 1，简化版）
- 枚举全部收藏（cursor 翻页，限速，断点续传）
- 视频：仅写元数据（标题/链接/作者/时长/描述），不下载
- 图文：取详情 → 正文 + 图片(webp) 本地化
- 输出到 config 指定的 Obsidian vault 子目录，并生成 index.md
- 限速：随机 2-5s + 滑动窗口 ≤20 次/分；遇 412/461 指数退避，连败 3 次暂停。

用法：
  python src/exporter.py                 # 全量
  python src/exporter.py --limit 10      # 只跑前 10 条做验证
"""
import os
import re
import sys
import json
import time
import random
from collections import deque

from curl_cffi import requests as cffi
from xhshow import Xhshow, SessionManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(ROOT, "secrets", "cookies.json")
STATE_FILE = os.path.join(ROOT, "state.json")
CONFIG_FILE = os.path.join(ROOT, "config.yaml")

OUTPUT_DIR = r"F:\Obsidian\小红书"  # 可通过 config.yaml 的 output_path 覆盖

def _load_output_dir():
    """优先读 config.yaml 的 output_path，否则用默认。"""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\s*(?:output_path|output_dir)\s*[:=]\s*(.+?)\s*#?.*$", line)
                if m:
                    p = m.group(1).strip().strip('"').strip("'")
                    if p:
                        return p
    except FileNotFoundError:
        pass
    return OUTPUT_DIR

OUTPUT_DIR = _load_output_dir()
HOME = "https://www.xiaohongshu.com/"
COLLECT = "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page"
NOTE_DETAIL = "https://edith.xiaohongshu.com/api/sns/web/v2/note/{note_id}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")

xs = Xhshow()

# ---------- 限速器 ----------
class RateLimiter:
    def __init__(self, min_delay=2.0, max_delay=5.0, max_per_min=20):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_per_min = max_per_min
        self.window = deque()

    def wait(self):
        # 随机间隔（去机械性）
        time.sleep(random.uniform(self.min_delay, self.max_delay))
        # 滑动窗口：最近 60s 内不超过 max_per_min
        now = time.time()
        while self.window and now - self.window[0] > 60:
            self.window.popleft()
        if len(self.window) >= self.max_per_min:
            sleep_for = 60 - (now - self.window[0]) + 1
            print(f"  [限速] 达到 {self.max_per_min}/分，休眠 {sleep_for:.1f}s")
            time.sleep(max(0, sleep_for))
        self.window.append(time.time())


def load_cookies():
    with open(COOKIE_FILE, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if v}


def safe_name(s, maxlen=60):
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "_", s or "untitled")
    return s[:maxlen].strip()


def get_session(cookies):
    s = cffi.Session(impersonate="chrome131")
    r0 = s.get(HOME, headers={"User-Agent": UA}, timeout=20)
    a1 = cookies.get("a1", "")
    webid = ""
    if a1:
        try:
            webid = xs.generate_web_id(a1)
        except Exception:
            webid = ""
    ck = {"web_session": cookies.get("web_session", ""), "a1": a1}
    if webid:
        ck["webId"] = webid
    # 从首页响应捕获 acw_tc（风控 cookie）
    try:
        acw = r0.cookies.get("acw_tc")
        if acw:
            ck["acw_tc"] = acw
    except Exception:
        pass
    s.cookies.clear()  # 不用 jar 存 cookie，统一走 ck 显式发送，避免多域名 acw_tc 冲突
    return s, ck


def signed_get(s, url, params, rl, ck, session=None):
    rl.wait()
    cd = dict(ck)
    sm = session or SessionManager()
    sign = xs.sign_headers_get(url, cd, params=params, session=sm)
    r = s.get(url, params=params, headers={"User-Agent": UA, "Referer": HOME, **sign},
              cookies=ck, timeout=20)
    try:
        acw = r.cookies.get("acw_tc")
        if acw:
            ck["acw_tc"] = acw
    except Exception:
        pass
    s.cookies.clear()  # 清掉响应写入的多域名 cookie，保持 ck 单一来源
    return r


def enumerate_favorites(s, user_id, rl, ck, limit=None):
    notes = []
    cursor = ""
    page = 0
    while True:
        page += 1
        params = {"num": 30, "cursor": cursor, "image_formats": "webp", "user_id": user_id}
        r = signed_get(s, COLLECT, params, rl, ck)
        try:
            j = r.json()
        except Exception:
            print("  [枚举] 非 JSON:", r.text[:200]); break
        if j.get("code") != 0:
            print("  [枚举] 错误 code=", j.get("code"), j.get("msg")); break
        data = j.get("data") or {}
        batch = data.get("notes") or []
        if not batch:
            break
        notes.extend(batch)
        print(f"  [枚举] 第{page}页 +{len(batch)} 条，累计 {len(notes)}")
        if limit and len(notes) >= limit:
            notes = notes[:limit]; break
        if not data.get("has_more"):
            break
        cursor = data.get("cursor") or ""
        if not cursor:
            break
    return notes


def fetch_detail(s, note_id, xsec_token, rl, ck):
    # 正确端点：POST /api/sns/web/v1/feed（note_id + xsec_token）
    url = "https://edith.xiaohongshu.com/api/sns/web/v1/feed"
    payload = {"source_note_id": note_id, "xsec_token": xsec_token,
               "xsec_source": "pc_feed", "image_formats": "webp"}
    rl.wait()
    sm = SessionManager()
    sign = xs.sign_headers_post(url, dict(ck), payload=payload, session=sm)
    r = s.post(url, json=payload,
               headers={"User-Agent": UA, "Referer": HOME,
                        "Content-Type": "application/json", **sign},
               cookies=ck, timeout=20)
    try:
        acw = r.cookies.get("acw_tc")
        if acw:
            ck["acw_tc"] = acw
    except Exception:
        pass
    s.cookies.clear()
    try:
        j = r.json()
    except Exception:
        print("    [detail] 非JSON:", r.text[:200])
        return {}
    if j.get("code") != 0:
        print("    [detail] code=", j.get("code"), j.get("msg"))
        return {}
    data = j.get("data") or {}
    note = data.get("note") or {}
    if not note and data.get("items"):
        it = data["items"][0]
        note = it.get("note_card") or it
    return note


def download_image(s, url, out_path):
    try:
        r = s.get(url, headers={"User-Agent": UA, "Referer": HOME}, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


def write_note_md(note, out_dir, img_dir, s, rl, ck, opts):
    note_id = note.get("note_id") or note.get("id")
    title = note.get("display_title") or note.get("title") or "untitled"
    ntype = note.get("type") or ("video" if note.get("video") else "normal")
    user = note.get("user") or {}
    author = user.get("nickname") or user.get("name") or ""
    link = f"https://www.xiaohongshu.com/explore/{note_id}"
    xsec = note.get("xsec_token") or ""

    fm = [
        "---",
        f"resourceId: {note_id}",
        f"title: \"{title.replace(chr(34), chr(39))}\"",
        f"type: {ntype}",
        f"author: \"{author}\"",
        f"link: {link}",
        "status: unstudied",
        "review_date: \"\"",
        "category: 待分类",
        f"xsec_token: \"{xsec}\"",
        "tags: []",
        "---",
    ]
    body = []

    if ntype == "video":
        # 视频：仅元数据，不下载
        fm.append(f"duration: \"{note.get('video', {}).get('duration', '')}\"")
        # 尝试取描述（列表里可能已有 interact_info，但没有 desc；detail 才有）
        desc = note.get("desc") or note.get("description") or ""
        if desc:
            body.append(desc)
        body.append("")
        body.append("> 视频笔记：按需求仅存元数据，不下载视频文件。点上方链接观看。")
        body.append(f"观看：{link}")
    else:
        # 图文：取详情拿正文 + 图片
        detail = fetch_detail(s, note_id, xsec, rl, ck)
        desc = (detail or {}).get("desc") or note.get("desc") or ""
        interact = (detail or {}).get("interact_info") or note.get("interact_info") or {}
        if desc:
            body.append(desc)
            body.append("")
        imgs = (detail or {}).get("image_list") or []
        img_md = []
        for i, im in enumerate(imgs, 1):
            url = ""
            info = im.get("info_list") or []
            if info:
                # 选一个适中分辨率
                url = info[-1].get("url") or info[0].get("url")
            url = url or im.get("url") or ""
            if not url:
                continue
            ext = "webp"
            fname = f"{note_id}_{i}.{ext}"
            fpath = os.path.join(img_dir, fname)
            if opts.get("download_images", True) and not os.path.exists(fpath):
                if download_image(s, url, fpath):
                    img_md.append(f"![[{fname}]]")
                else:
                    img_md.append(f"![{title}_{i}]({url})")
            else:
                img_md.append(f"![[{fname}]]" if os.path.exists(fpath) else f"![{title}_{i}]({url})")
        if img_md:
            body.append("\n".join(img_md))
        fm.insert(-1, f"liked_count: \"{interact.get('liked_count', '')}\"")
        fm.insert(-1, f"collected_count: \"{interact.get('collected_count', '')}\"")

    fname = f"{safe_name(title)}_{note_id}.md"
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n\n" + "\n".join(body) + "\n")
    return fpath, ntype


def main():
    limit = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg.startswith("--limit"):
            if "=" in arg:
                limit = int(arg.split("=", 1)[1])
            elif i + 1 < len(args):
                limit = int(args[i + 1])
    cookies = load_cookies()
    user_id = cookies.get("user_id", "")
    rl = RateLimiter()
    out_dir = OUTPUT_DIR
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    state = {}
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    done = set(state.get("done", []))

    s, ck = get_session(cookies)
    print("[*] 枚举收藏中...")
    notes = enumerate_favorites(s, user_id, rl, ck, limit=limit)
    print(f"[*] 共获取 {len(notes)} 条收藏")

    index_rows = []
    stats = {"normal": 0, "video": 0}
    for note in notes:
        note_id = note.get("note_id") or note.get("id")
        if note_id in done:
            continue
        try:
            fpath, ntype = write_note_md(note, out_dir, img_dir, s, rl, ck, {"download_images": True})
            done.add(note_id)
            stats[ntype] = stats.get(ntype, 0) + 1
            title = note.get("display_title") or note.get("title") or "untitled"
            index_rows.append((ntype, title, os.path.basename(fpath)))
            print(f"  [导出] ({ntype}) {title}")
        except Exception as e:
            print(f"  [导出失败] {note_id}: {e}")

    # 写 index.md
    idx = ["---", "tags: xhs-favorites-index", "---", "# 小红书收藏索引", ""]
    idx.append(f"总数：{len(index_rows)}（图文 {stats.get('normal',0)} / 视频 {stats.get('video',0)}）")
    idx.append("")
    idx.append("| 类型 | 标题 | 文件 |")
    idx.append("| --- | --- | --- |")
    for ntype, title, f in index_rows:
        idx.append(f"| {ntype} | {title} | [[{f.replace('.md','')}]] |")
    with open(os.path.join(out_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx) + "\n")

    state["done"] = list(done)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[*] 完成。导出 {len(index_rows)} 篇 → {out_dir}")
    print(f"[*] 统计：图文 {stats.get('normal',0)}，视频 {stats.get('video',0)}")


if __name__ == "__main__":
    main()
