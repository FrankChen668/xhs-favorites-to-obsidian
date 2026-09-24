"""我的动态/笔记采集器（已验证 ✅）：GET /v1/user_posted（单用户）"""
import logging
from .base import Collector, normalize

logger = logging.getLogger("xhs.collectors.user_notes")


class UserNotesCollector(Collector):
    source = "user_notes"

    def collect(self, client, cfg: dict, limit: int = None) -> list:
        target = cfg.get("target_user_id") or client.user_id
        if not target:
            logger.warning("[动态] 缺少 target_user_id 且 cookie 无 user_id，跳过")
            return []
        out = []
        cursor = ""
        seen = set()
        while True:
            params = {"user_id": target, "num": cfg.get("num_per_page", 30),
                      "cursor": cursor, "image_formats": "webp"}
            j = client.request("GET", "v1/user_posted", params=params)
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
            logger.info("[动态] 累计 %d 条", len(out))
            if limit and len(out) >= limit:
                out = out[:limit]
                break
            if not data.get("has_more"):
                break
            cursor = data.get("cursor") or ""
            if not cursor:
                break
        return out
