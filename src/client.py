"""
client.py —— XHSClient 传输层（V2 重构）
职责：cookie 管理 + xhshow 纯 Python 签名 + curl_cffi 指纹请求 + 限速 + 重试/退避 + 熔断。
所有参数来自 config，不在代码里写死默认值（安全兜底下限除外）。
"""
import time
import random
import logging
from collections import deque

from curl_cffi import requests as cffi
from xhshow import Xhshow, SessionManager

logger = logging.getLogger("xhs.client")

HOME = "https://www.xiaohongshu.com/"
EDITH = "https://edith.xiaohongshu.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")

# 安全下限：即使配置乱填，单次最大限速也不低于此（防误伤账号）
SAFE_MIN_RPM = 5


class RateLimiter:
    def __init__(self, cfg: dict):
        self.min_delay = float(cfg.get("min_delay", 2.0))
        self.max_delay = float(cfg.get("max_delay", 5.0))
        self.max_per_min = max(SAFE_MIN_RPM, int(cfg.get("requests_per_min", 20)))
        self.window = deque()

    def wait(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))
        now = time.time()
        while self.window and now - self.window[0] > 60:
            self.window.popleft()
        if len(self.window) >= self.max_per_min:
            sleep_for = 60 - (now - self.window[0]) + 1
            logger.warning("[限速] 达到 %d/分，休眠 %.1fs", self.max_per_min, sleep_for)
            time.sleep(max(0, sleep_for))
        self.window.append(time.time())


class CircuitBreaker:
    def __init__(self, cfg: dict):
        self.threshold = int(cfg.get("fail_threshold", 3))
        self.pause_min = int(cfg.get("pause_minutes", 15))
        self.fail_count = 0
        self.paused_until = 0

    def on_fail(self):
        self.fail_count += 1
        if self.fail_count >= self.threshold:
            self.paused_until = time.time() + self.pause_min * 60
            logger.error("[熔断] 连续失败 %d 次，暂停 %d 分钟", self.threshold, self.pause_min)
            self.fail_count = 0

    def on_success(self):
        self.fail_count = 0

    def check(self):
        if time.time() < self.paused_until:
            wait = self.paused_until - time.time()
            logger.warning("[熔断] 仍在暂停，等待 %.0fs", wait)
            time.sleep(wait)


class XHSClient:
    def __init__(self, cookies: dict, rate_cfg: dict, backoff_cfg: dict, cb_cfg: dict):
        self.cookies = {k: v for k, v in cookies.items() if v}
        self.user_id = self.cookies.get("user_id", "")
        self.xs = Xhshow()
        self.sm = SessionManager()
        self.rl = RateLimiter(rate_cfg)
        self.cb = CircuitBreaker(cb_cfg)
        self.backoff = backoff_cfg
        self.trigger_codes = set(backoff_cfg.get("trigger_codes", [412, 461, 300012]))
        self.max_retries = int(backoff_cfg.get("max_retries", 3))
        self.base_seconds = float(backoff_cfg.get("base_seconds", 10))
        self.session = cffi.Session(impersonate="chrome131")
        self._init_session()

    def _init_session(self):
        r0 = self.session.get(HOME, headers={"User-Agent": UA}, timeout=20)
        a1 = self.cookies.get("a1", "")
        if a1:
            try:
                webid = self.xs.generate_web_id(a1)
                if webid:
                    self.cookies["webId"] = webid
            except Exception:
                pass
        try:
            acw = r0.cookies.get("acw_tc")
            if acw:
                self.cookies["acw_tc"] = acw
        except Exception:
            pass
        self.session.cookies.clear()  # 统一走显式 ck 发送，避免多域名 acw_tc 冲突

    def _capture_acw(self, resp):
        try:
            acw = resp.cookies.get("acw_tc")
            if acw:
                self.cookies["acw_tc"] = acw
        except Exception:
            pass

    def _signed_get(self, path: str, params: dict):
        url = f"{EDITH}/api/sns/web/{path}"
        sign = self.xs.sign_headers_get(url, dict(self.cookies), params=params, session=self.sm)
        r = self.session.get(url, params=params,
                             headers={"User-Agent": UA, "Referer": HOME, **sign},
                             cookies=self.cookies, timeout=20)
        self._capture_acw(r)
        self.session.cookies.clear()
        return r

    def _signed_post(self, path: str, payload: dict):
        url = f"{EDITH}/api/sns/web/{path}"
        sign = self.xs.sign_headers_post(url, dict(self.cookies), payload=payload, session=self.sm)
        r = self.session.post(url, json=payload,
                              headers={"User-Agent": UA, "Referer": HOME,
                                       "Content-Type": "application/json", **sign},
                              cookies=self.cookies, timeout=20)
        self._capture_acw(r)
        self.session.cookies.clear()
        return r

    def request(self, method: str, path: str, params=None, payload=None):
        """带限速 + 重试/退避 + 熔断的统一入口。返回解析后的 dict（失败返回 None）。"""
        self.cb.check()
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            self.rl.wait()
            try:
                if method == "GET":
                    r = self._signed_get(path, params or {})
                else:
                    r = self._signed_post(path, payload or {})
            except Exception as e:
                last_err = e
                logger.warning("[请求] 异常 %s (第%d次): %s", path, attempt, e)
                self._backoff(attempt)
                continue
            try:
                j = r.json()
            except Exception:
                last_err = f"非JSON status={r.status_code}"
                logger.warning("[请求] 非JSON %s: %s", path, r.text[:120])
                self._backoff(attempt)
                continue
            code = j.get("code")
            if code == 0:
                self.cb.on_success()
                return j
            if code in self.trigger_codes or code in (-100, -101):
                last_err = f"code={code} msg={j.get('msg')}"
                logger.warning("[请求] 风控/错误 %s (第%d次): %s", path, attempt, last_err)
                self.cb.on_fail()
                self._backoff(attempt)
                continue
            # 其他业务错误（如 -3 参数错），不重试，直接返回
            logger.error("[请求] 业务错误 %s: code=%s msg=%s", path, code, j.get("msg"))
            return j
        logger.error("[请求] 放弃 %s: %s", path, last_err)
        return None

    def _backoff(self, attempt: int):
        sec = self.base_seconds * (2 ** (attempt - 1))
        logger.info("[退避] %ds", sec)
        time.sleep(sec)

    # ---- 业务便捷方法 ----
    def get_note_detail(self, note_id: str, xsec_token: str) -> dict:
        """POST /v1/feed 取单篇详情（图文正文+图片 / 视频元数据）。"""
        payload = {"source_note_id": note_id, "xsec_token": xsec_token,
                   "xsec_source": "pc_feed", "image_formats": "webp"}
        j = self.request("POST", "v1/feed", payload=payload)
        if not j:
            return {}
        data = j.get("data") or {}
        note = data.get("note") or {}
        if not note and data.get("items"):
            note = (data["items"][0] or {}).get("note_card") or data["items"][0] or {}
        return note

    def download_binary(self, url: str, timeout: int = 60) -> bytes | None:
        """下载图片/视频二进制（不走签名，直接用会话，Referer 防盗链）。"""
        try:
            r = self.session.get(url, headers={"User-Agent": UA, "Referer": HOME}, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 100:
                return r.content
        except Exception as e:
            logger.warning("[下载] 失败 %s: %s", url[:60], e)
        return None
