"""搜索采集器（已验证 ✅）：POST /v1/search/notes"""
import time
import logging
from .base import Collector, normalize

logger = logging.getLogger("xhs.collectors.search")


class SearchCollector(Collector):
    source = "search"

    def collect(self, client, cfg: dict, limit: int = None) -> list:
        keywords = cfg.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [keywords]
        if not keywords:
            logger.warning("[搜索] 未配置 keywords，跳过")
            return []
        max_pages = int(cfg.get("max_pages", 5))
        sort = cfg.get("sort", "general")
        out = []
        seen = set()
        for kw in keywords:
            cursor = ""
            for page in range(1, max_pages + 1):
                payload = {"keyword": kw, "page": page, "page_size": 20,
                           "search_id": "v2_" + str(int(time.time() * 1000)),
                           "sort": sort, "note_type": 0, "ext_flags": [],
                           "image_formats": ["jpg", "webp", "avif"]}
                j = client.request("POST", "v1/search/notes", payload=payload)
                if not j:
                    break
                data = j.get("data") or {}
                items = data.get("items") or []
                if not items:
                    break
                for it in items:
                    rec = normalize(it, self.source, keyword=kw)
                    if rec and rec.note_id not in seen:
                        seen.add(rec.note_id)
                        out.append(rec)
                logger.info("[搜索] 关键词=%s 第%d页 累计 %d 条", kw, page, len(out))
                if limit and len(out) >= limit:
                    out = out[:limit]
                    break
                if not data.get("has_more"):
                    break
                # 搜索翻页用 cursor（部分版本没有，则靠 page）
                cursor = data.get("cursor") or ""
        return out
