"""
main.py —— V2 入口：按配置装配采集器 → 导出 Obsidian MD → 后处理（分类/索引/看板）
用法：
  python src/main.py
  python src/main.py --collectors.search.enabled true --collectors.search.keywords "AI Agent" "Obsidian"
  python src/main.py --media.video.mode download --limit 3
  python src/main.py --post-process.auto-classify false
"""
import os
import sys
import json
import logging

from .config import load_config, resolve_paths, load_cookies
from .client import XHSClient
from .collectors import (FavoritesCollector, SearchCollector, UserNotesCollector,
                         FeedCollector, NoteRecord)
from . import exporter as exporter_mod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("xhs.main")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, "state.json")


def build_collectors(cfg: dict, client) -> list:
    cs = cfg.get("collectors", {})
    out = []
    if cs.get("favorites", {}).get("enabled"):
        out.append(FavoritesCollector())
    if cs.get("search", {}).get("enabled"):
        out.append(SearchCollector())
    if cs.get("user_notes", {}).get("enabled"):
        out.append(UserNotesCollector())
    ch = cs.get("explore", {})
    if ch.get("enabled"):
        out.append(FeedCollector("explore", "discover_feed"))
    fl = cs.get("following", {})
    if fl.get("enabled"):
        out.append(FeedCollector("following", "following"))
    return out


def load_state() -> set:
    if os.path.exists(STATE_FILE):
        try:
            d = json.load(open(STATE_FILE, encoding="utf-8"))
            return set(d.get("done", []))
        except Exception:
            pass
    return set()


def save_state(done: set):
    json.dump({"done": list(done)}, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def regenerate_index(output_dir: str, group_by: str = "category"):
    import re
    files = [f for f in os.listdir(output_dir) if f.endswith(".md") and f != "index.md"]
    rows = []
    for f in files:
        t = open(os.path.join(output_dir, f), encoding="utf-8").read()
        def get(field):
            m = re.search(rf"^{field}:\s*(.+)$", t, re.M)
            return m.group(1).strip().strip('"') if m else ""
        rows.append((get("category"), get("source"), get("type"), get("title"), f))
    # 分组
    groups = {}
    for cat, src, ntype, title, f in rows:
        key = cat or "未分类" if group_by == "category" else (src or "other")
        groups.setdefault(key, []).append((ntype, title, f))
    lines = ["---", "tags: xhs-index", "---", "# 小红书导出索引", "",
             f"总数：{len(rows)}（图文 {sum(1 for r in rows if r[2]!='video')} / 视频 {sum(1 for r in rows if r[2]=='video')}）", ""]
    for g in sorted(groups.keys()):
        lines.append(f"## {g}（{len(groups[g])}）")
        lines.append("")
        lines.append("| 类型 | 标题 | 文件 |")
        lines.append("| --- | --- | --- |")
        for ntype, title, f in groups[g]:
            lines.append(f"| {ntype} | {title} | [[{f.replace('.md','')}]] |")
        lines.append("")
    open(os.path.join(output_dir, "index.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    cfg = resolve_paths(load_config())
    logging.getLogger().setLevel(getattr(logging, cfg.get("log_level", "INFO")))
    logger.info("输出目录：%s", cfg["output_dir"])
    os.makedirs(cfg["output_dir"], exist_ok=True)
    img_dir = os.path.join(cfg["output_dir"], "images")
    vid_dir = os.path.join(cfg["output_dir"], cfg["media"]["video"]["download_dir"])
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(vid_dir, exist_ok=True)

    cookies = load_cookies(cfg["cookie_file"])
    rl_cfg = cfg["rate_limit"]
    client = XHSClient(cookies, rl_cfg, rl_cfg.get("backoff", {}), rl_cfg.get("circuit_breaker", {}))

    limit = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--limit"):
            if "=" in arg:
                limit = int(arg.split("=", 1)[1])
            elif i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 2])

    collectors = build_collectors(cfg, client)
    if not collectors:
        logger.warning("没有启用的采集器（favorites 默认启用）。检查 config.yaml。")
        return

    # 采集
    all_records = []
    for col in collectors:
        logger.info("=== 开始采集：%s ===", col.source)
        recs = col.collect(client, cfg.get("collectors", {}).get(col.source, {}), limit=limit)
        logger.info("[%s] 采集到 %d 条", col.source, len(recs))
        all_records.extend(recs)

    # 去重（跨采集器）
    seen = set()
    uniq = []
    for r in all_records:
        k = f"{r.source}:{r.note_id}"
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    logger.info("去重后共 %d 条", len(uniq))

    # 导出
    done = load_state() if cfg.get("resume", True) else set()
    index_rows = []
    stats = {}
    for rec in uniq:
        try:
            fname, ntype = exporter_mod.export_note(rec, client, cfg["output_dir"], img_dir, vid_dir,
                                                   cfg["media"], done)
            if fname:
                stats[ntype] = stats.get(ntype, 0) + 1
                index_rows.append((rec.source, ntype, rec.title, fname))
                logger.info("[导出] (%s/%s) %s", rec.source, ntype, rec.title)
        except Exception as e:
            logger.error("[导出失败] %s: %s", rec.note_id, e)

    save_state(done)
    logger.info("[*] 完成。导出 %d 篇（图文 %d / 视频 %d）", len(index_rows),
                stats.get("normal", 0), stats.get("video", 0))

    pp = cfg.get("post_process", {})
    if pp.get("regenerate_index", True):
        regenerate_index(cfg["output_dir"], group_by="category" if pp.get("auto_classify", True) else "source")
        logger.info("[*] 已生成 index.md")
    if pp.get("auto_classify", True):
        try:
            from . import classify
            classify.run(cfg["output_dir"])
            logger.info("[*] 已自动分类")
        except Exception as e:
            logger.warning("[分类] 跳过：%s", e)


if __name__ == "__main__":
    main()
