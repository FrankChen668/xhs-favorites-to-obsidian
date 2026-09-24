"""发现/推荐流 与 关注流采集器（已验证 ✅）：POST /v1/homefeed
- explore  : search_page_request_source = discover_feed
- following: search_page_request_source = following
两者共用同一端点，仅 source 字段与 request_source 不同。
"""
import logging
from .base import Collector, normalize

logger = logging.getLogger("xhs.collectors.feed")

SRC_MAP = {"recommend": "discover_feed", "explore": "discover_feed", "following": "following"}


class FeedCollector(Collector):
    # source 由构造时指定
    def __init__(self, source: str, request_source: str):
        self.source = source
        self.request_source = request_source

    def collect(self, client, cfg: dict, limit: int = None) -> list:
        max_pages = int(cfg.get("max_pages", 5))
        out = []
        seen = set()
        cursor_score = ""
        for page in range(1, max_pages + 1):
            payload = {"num": 20, "cursor_score": cursor_score, "refresh_type": 1,
                       "note_index": 0, "unread_begin_note_id": "", "unread_end_note_id": "",
                       "unread_note_count": 0, "search_page_request_source": self.request_source}
            j = client.request("POST", "v1/homefeed", payload=payload)
            if not j:
                break
            data = j.get("data") or {}
            items = data.get("items") or []
            if not items:
                break
            for it in items:
                rec = normalize(it, self.source)
                if rec and rec.note_id not in seen:
                    seen.add(rec.note_id)
                    out.append(rec)
            logger.info("[%s] 第%d页 累计 %d 条", self.source, page, len(out))
            if limit and len(out) >= limit:
                out = out[:limit]
                break
            nxt = data.get("cursor_score") or ""
            has_more = data.get("has_more")
            if has_more is False:
                break
            if not nxt:
                if has_more is None:
                    logger.info("[%s] 无 cursor_score，停止翻页", self.source)
                    break
            cursor_score = nxt
        return out
