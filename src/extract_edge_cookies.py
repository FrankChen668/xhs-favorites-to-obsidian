"""
Edge 本地 Cookie 提取器（仅读取本机 Edge 已登录的 xiaohongshu cookie）
用途：免去手动从 DevTools 复制 web_session / a1 的麻烦。
安全：仅读取本地 Edge 加密 Cookie 库并用 Windows DPAPI 本地解密，不外传任何数据。
依赖：pywin32（Windows 自带 DPAPI 封装）；本脚本需在 Windows 上运行。
输出：写入 ../secrets/cookies.json（已被 .gitignore 忽略，不会提交）
"""
import os
import sys
import json
import shutil
import sqlite3

import win32crypt

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.join(PROJECT, "secrets")
OUT = os.path.join(SECRETS, "cookies.json")


def locate_edge_cookie_db():
    """定位 Edge 的 Cookies SQLite 库，优先 Default 配置、新版 Network 子目录。"""
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
    candidates = [
        os.path.join(base, "Default", "Network", "Cookies"),
        os.path.join(base, "Default", "Cookies"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def decrypt_value(encrypted):
    """用 Windows DPAPI 解密 Edge 存储的加密 cookie 值。"""
    try:
        if not encrypted:
            return ""
        data = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)
        return data[1].decode("utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        return f"<decrypt-failed:{e}>"


def main():
    db = locate_edge_cookie_db()
    if not db:
        print("ERROR: 未找到 Edge Cookie 数据库，请确认 Edge 已安装且至少登录过一次。")
        sys.exit(1)
    print(f"找到 Edge Cookie 库: {db}")

    # 复制一份再读，避免 Edge 进程占用导致 SQLite 锁
    tmp = os.path.join(SECRETS, "_edge_cookies_tmp.db")
    shutil.copy2(db, tmp)
    try:
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT host_key, name, value, encrypted_value "
            "FROM cookies WHERE host_key LIKE '%xiaohongshu.com%'"
        ).fetchall()
        conn.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    cookies = {}
    for host, name, value, enc in rows:
        if name in ("web_session", "a1"):
            v = value if value else decrypt_value(enc)
            cookies[name] = v
            print(f"  [OK] {name}  (host={host})  长度={len(v)}")
    if "web_session" not in cookies or "a1" not in cookies:
        print("ERROR: 未找到 web_session / a1，请确认 Edge 中 xiaohongshu.com 已登录。")
        sys.exit(2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"\n已写入: {OUT}")
    print("下一步：运行  python src/probe.py   做连通性探针。")


if __name__ == "__main__":
    main()
