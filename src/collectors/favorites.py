"""收藏采集器（已验证 ✅）：GET /v2/note/collect/page"""
import logging
from .base import Collector, normalize

logger = logging.getLogger("xhs.collectors.favorites")


class FavoritesCollector(Collector):
    source = "favorites"

    def collect(self, client, cfg: dict, limit: int = None) -> list:
        out = []
        cursor = ""
        seen = set()
        while True:
            params = {"num": cfg.get("num_per_page", 30), "cursor": cursor,
                      "image_formats": "webp", "user_id": client.user_id}
            j = client.request("GET", "v2/note/collect/page", params=params)
            if not j:
                break
            data = j.get("data") or {}
            batch = data.get("notes") or []
            if not batch:
                break
            for n in batch:
                rec = normalize(n, self.source)
                if rec and rec.note_id not in seen:
                    seen.add(rec.note_id)
                    out.append(rec)
            logger.info("[收藏] 累计 %d 条", len(out))
            if limit and len(out) >= limit:
                out = out[:limit]
                break
            if not data.get("has_more"):
                break
            cursor = data.get("cursor") or ""
            if not cursor:
                break
        return out
