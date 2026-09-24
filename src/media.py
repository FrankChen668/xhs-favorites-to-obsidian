"""
media.py —— 媒体处理（V2）
- 图片：下载 + 按配置转 webp / 限制宽度 / 质量（用 Pillow）
- 视频：mode=link_only 仅元数据；mode=download 下载 mp4（带体积上限）
"""
import os
import json
import logging
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger("xhs.media")


def process_image(client, url: str, out_path: str, opts: dict) -> str | None:
    """下载并按配置处理图片，返回最终写入的（相对）文件名或 None。"""
    fmt = (opts.get("format") or "webp").lower()
    max_width = int(opts.get("max_width", 1080))
    quality = int(opts.get("quality", 82))
    data = client.download_binary(url)
    if not data:
        return None
    if fmt == "keep" or not Image:
        # 原样保存
        ext = os.path.splitext(url.split("!")[0].split("?")[0])[1] or ".jpg"
        final = out_path + ext
        with open(final, "wb") as f:
            f.write(data)
        return os.path.basename(final)
    try:
        im = Image.open(BytesIO(data)).convert("RGB")
        if im.width > max_width:
            h = int(im.height * max_width / im.width)
            im = im.resize((max_width, h))
        final = out_path + ".webp"
        im.save(final, "WEBP", quality=quality)
        return os.path.basename(final)
    except Exception as e:
        logger.warning("[图片] 转码失败，原样保存: %s", e)
        final = out_path + ".jpg"
        with open(final, "wb") as f:
            f.write(data)
        return os.path.basename(final)


def extract_video_url(note_detail: dict) -> tuple:
    """从笔记详情提取视频播放地址与时长。返回 (url, duration)。
    视频地址藏在 video.media_v2（JSON 字符串）→ video.stream.h264[0].master_url。
    """
    video = note_detail.get("video") or {}
    mv2 = video.get("media_v2")
    if isinstance(mv2, str):
        try:
            mv2 = json.loads(mv2)
        except Exception:
            mv2 = {}
    duration = ""
    if isinstance(mv2, dict):
        duration = mv2.get("video", {}).get("duration") or ""
    streams = mv2.get("stream") if isinstance(mv2, dict) else {}
    url = ""
    for codec in ("h264", "h265"):
        for st in streams.get(codec, []):
            u = st.get("master_url") or (st.get("backup_urls") or [None])[0]
            if u:
                url = u
                break
        if url:
            break
    if not url and isinstance(mv2, dict):
        # 兜底：media_v2.media 或顶层 media 可能直接带 url
        media = mv2.get("media") or video.get("media") or {}
        if isinstance(media, dict):
            url = media.get("url") or media.get("master_url") or ""
    return url, duration


def process_video(client, note_detail: dict, out_path: str, opts: dict) -> tuple:
    """下载视频（mode=download）。返回 (final_filename_or_None, duration, note)。"""
    url, duration = extract_video_url(note_detail)
    if not url:
        return None, duration, "无可用视频地址"
    max_mb = float(opts.get("max_size_mb", 500))
    data = client.download_binary(url, timeout=120)
    if not data:
        return None, duration, "下载失败"
    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_mb:
        return None, duration, f"超过 {max_mb}MB 上限（{size_mb:.1f}MB），仅留链接"
    final = out_path + ".mp4"
    with open(final, "wb") as f:
        f.write(data)
    return os.path.basename(final), duration, f"已下载 {size_mb:.1f}MB"
