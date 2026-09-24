"""
exporter.py —— 把 NoteRecord 写成 Obsidian Markdown（V2）
- 图文：调详情补全正文 + 图片（经 media 处理）
- 视频：按 media.video.mode 决定仅元数据 或 下载 mp4
- 输出 frontmatter + 正文 + 图片/视频嵌入，配合 Obsidian + Dataview
"""
import os
import re
import logging

from . import media as media_mod

logger = logging.getLogger("xhs.exporter")

IMG_EXT = (".webp", ".jpg", ".png", ".jpeg")


def safe_name(s: str, maxlen=60) -> str:
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "_", s or "untitled")
    return s[:maxlen].strip()


def _write_md(out_dir: str, rec, body_lines: list, extra_fm: list) -> str:
    title = rec.title
    fm = [
        "---",
        f"resourceId: {rec.note_id}",
        f"title: \"{title.replace(chr(34), chr(39))}\"",
        f"type: {rec.type}",
        f"author: \"{rec.author}\"",
        f"link: {rec.link}",
        f"source: {rec.source}",
        f"status: unstudied",
        "review_date: \"\"",
        "category: 待分类",
        f"xsec_token: \"{rec.xsec_token}\"",
        "tags: []",
    ] + extra_fm + ["---"]
    fname = f"{safe_name(title)}_{rec.note_id}.md"
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n\n" + "\n".join(body_lines) + "\n")
    return fname


def export_note(rec, client, out_dir: str, img_dir: str, vid_dir: str, media_cfg: dict, state_done: set) -> tuple:
    key = f"{rec.source}:{rec.note_id}"
    if key in state_done:
        return None, rec.type
    note_id = rec.note_id
    img_cfg = media_cfg.get("images", {})
    vid_cfg = media_cfg.get("video", {})
    body = []
    extra_fm = []
    ntype = rec.type

    if ntype == "video":
        duration = rec.video.get("duration") if isinstance(rec.video, dict) else ""
        if vid_cfg.get("mode") == "download":
            detail = client.get_note_detail(note_id, rec.xsec_token)
            fname, _, note = media_mod.process_video(client, detail, os.path.join(vid_dir, note_id), vid_cfg)
            if fname:
                body.append(f"![[{fname}]]")
                extra_fm.append(f"video_file: \"{fname}\"")
            else:
                body.append(f"> 视频下载跳过（{note}）。观看：{rec.link}")
            if duration:
                extra_fm.append(f"duration: \"{duration}\"")
        else:
            if duration:
                extra_fm.append(f"duration: \"{duration}\"")
            desc = rec.desc or ""
            if desc:
                body.append(desc)
            body.append("")
            body.append("> 视频笔记：按配置仅存元数据，不下载视频文件。点上方链接观看。")
            body.append(f"观看：{rec.link}")
    else:
        # 图文：详情补全正文 + 图片
        detail = client.get_note_detail(note_id, rec.xsec_token)
        if not detail:
            detail = {}
        desc = detail.get("desc") or rec.desc or ""
        if desc:
            body.append(desc)
            body.append("")
        # 图片：优先用详情的 image_list，回退到 rec.image_list
        imgs = detail.get("image_list") or []
        urls = []
        for im in imgs:
            if isinstance(im, dict):
                info = im.get("info_list") or []
                u = im.get("url") or (info[-1].get("url") if info else "")
                if u:
                    urls.append(u)
        if not urls:
            urls = rec.image_list
        img_md = []
        if img_cfg.get("enabled", True):
            for i, u in enumerate(urls, 1):
                out_base = os.path.join(img_dir, f"{note_id}_{i}")
                if os.path.exists(out_base + ".webp") or os.path.exists(out_base + ".jpg"):
                    # 已存在
                    for ext in IMG_EXT:
                        if os.path.exists(out_base + ext):
                            img_md.append(f"![[{note_id}_{i}{ext}]]")
                            break
                    continue
                fn = media_mod.process_image(client, u, out_base, img_cfg)
                if fn:
                    img_md.append(f"![[{fn}]]")
                else:
                    img_md.append(f"![{rec.title}_{i}]({u})")
        elif urls:
            img_md = [f"![{rec.title}_{i}]({u})" for i, u in enumerate(urls, 1)]
        if img_md:
            body.append("\n".join(img_md))
        interact = detail.get("interact_info") or rec.interact or {}
        if interact:
            extra_fm.append(f"liked_count: \"{interact.get('liked_count', '')}\"")
            extra_fm.append(f"collected_count: \"{interact.get('collected_count', '')}\"")

    fname = _write_md(out_dir, rec, body, extra_fm)
    state_done.add(key)
    return fname, ntype
