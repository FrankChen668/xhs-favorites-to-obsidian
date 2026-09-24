"""
collectors/base.py —— NoteRecord 与采集器抽象（V2）
统一解析：favorites / user_posted 的字段在 item 顶层；search / homefeed 的 note_id 在 id、xsec 在顶层、正文在 note_card。
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("xhs.collectors")

LINK = "https://www.xiaohongshu.com/explore/{note_id}"


@dataclass
class NoteRecord:
    note_id: str
    source: str                 # favorites | search | user_notes | explore | following
    title: str = "untitled"
    type: str = "normal"        # normal | video
    author: str = ""
    xsec_token: str = ""
    desc: str = ""              # 正文（可能缺，需详情补全）
    image_list: list = field(default_factory=list)   # 图片 URL 列表（部分来源已有）
    video: dict = field(default_factory=dict)        # 视频信息（时长等）
    cover_url: str = ""         # 封面
    interact: dict = field(default_factory=dict)
    keyword: str = ""           # 搜索来源时记录关键词

    @property
    def link(self):
        return LINK.format(note_id=self.note_id)


def normalize(item: dict, source: str, keyword: str = "") -> NoteRecord | None:
    """把任意来源的 item 规整为 NoteRecord。失败返回 None。"""
    if not isinstance(item, dict):
        return None
    note_id = item.get("id") or item.get("note_id")
    if not note_id:
        return None
    xsec = item.get("xsec_token") or item.get("xsec_source") or ""
    card = item.get("note_card") or item
    title = card.get("display_title") or card.get("title") or "untitled"
    ntype = card.get("type") or ("video" if card.get("video") else "normal")
    user = card.get("user") or {}
    author = user.get("nickname") or user.get("name") or ""
    desc = card.get("desc") or ""
    images = [im.get("url") for im in (card.get("image_list") or []) if isinstance(im, dict) and im.get("url")]
    # 若无 url 字段，尝试 info_list
    if not images:
        for im in (card.get("image_list") or []):
            if isinstance(im, dict):
                info = im.get("info_list") or []
                if info:
                    images.append(info[-1].get("url") or info[0].get("url"))
    cover = ""
    c = card.get("cover") or {}
    if isinstance(c, dict):
        cover = c.get("url_default") or c.get("url_pre") or c.get("url") or ""
    video = card.get("video") or {}
    interact = card.get("interact_info") or {}
    return NoteRecord(
        note_id=str(note_id), source=source, title=title, type=ntype, author=author,
        xsec_token=xsec, desc=desc, image_list=[u for u in images if u],
        video=video, cover_url=cover, interact=interact, keyword=keyword,
    )


class Collector:
    source = "base"

    def collect(self, client, cfg: dict, limit: int = None) -> list:
        """返回 NoteRecord 列表。子类实现。"""
        raise NotImplementedError
