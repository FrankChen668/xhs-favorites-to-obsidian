"""
config.py —— 配置加载与 CLI 覆盖（V2）
- 读取 config.yaml（含默认值兜底）
- 支持 CLI 点分覆盖：--rate-limit.requests-per-min 15 --collectors.search.enabled true
- 不引入环境变量（依决策）
"""
import os
import sys
import json
import logging

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger("xhs.config")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "cookie_file": "secrets/cookies.json",
    "output_dir": r"F:\Obsidian\小红书",
    "index_file": "index.md",
    "rate_limit": {
        "requests_per_min": 20,
        "min_delay": 2.0,
        "max_delay": 5.0,
        "concurrency": 1,
        "backoff": {"max_retries": 3, "base_seconds": 10, "trigger_codes": [412, 461, 300012]},
        "circuit_breaker": {"fail_threshold": 3, "pause_minutes": 15},
    },
    "collectors": {
        "favorites": {"enabled": True, "num_per_page": 30},
        "search": {"enabled": False, "keywords": [], "max_pages": 5, "sort": "general"},
        "user_notes": {"enabled": False, "target_user_id": "", "num_per_page": 30},
        "explore": {"enabled": False, "channel": "recommend", "max_pages": 5},
        "following": {"enabled": False, "max_pages": 5},
    },
    "media": {
        "images": {"enabled": True, "format": "webp", "max_width": 1080, "quality": 82, "skip_if_no_text": False},
        "video": {"mode": "link_only", "download_dir": "videos", "max_size_mb": 500, "expire_buffer_min": 30},
    },
    "post_process": {"auto_classify": True, "regenerate_index": True, "dataview_board": False},
    "resume": True,
    "log_level": "INFO",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_dot_path(d: dict, dotted: str, value):
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def _coerce(value: str):
    low = value.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", ""):
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_config(path: str = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    cfg_path = path or os.path.join(ROOT, "config.yaml")
    if os.path.exists(cfg_path) and yaml:
        with open(cfg_path, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, user_cfg)
    elif os.path.exists(cfg_path) and not yaml:
        logger.warning("未安装 pyyaml，仅使用内置默认配置（不读 config.yaml）")
    # CLI 覆盖
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            continue
        body = arg[2:]
        if "=" in body:
            k, v = body.split("=", 1)
        else:
            # 布尔开关形式 --collectors.search.enabled （后接值）或独立 flag 暂不支持
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                k, v = body, sys.argv[idx + 1]
            else:
                continue
        _set_dot_path(cfg, k, _coerce(v))
    return cfg


def resolve_paths(cfg: dict) -> dict:
    """把相对路径解析为绝对（相对于 ROOT）。"""
    cf = cfg.get("cookie_file")
    if cf and not os.path.isabs(cf):
        cfg["cookie_file"] = os.path.join(ROOT, cf)
    od = cfg.get("output_dir")
    if od and not os.path.isabs(od):
        cfg["output_dir"] = os.path.join(ROOT, od)
    return cfg


def load_cookies(cookie_file: str) -> dict:
    with open(cookie_file, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if v}


if __name__ == "__main__":
    c = resolve_paths(load_config())
    print(json.dumps(c, ensure_ascii=False, indent=2))
