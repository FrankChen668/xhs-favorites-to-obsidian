---
name: xhs-favorites-to-obsidian
description: 纯 Python、零浏览器（无 Chromium/Playwright）把小红书收藏夹（图文+视频）导出为 Obsidian Markdown 的流水线。覆盖 cookie 获取、x-s/x-t 签名、收藏枚举、笔记详情、图片 webp 本地化、风控限速。当用户说"导出小红书收藏""整理小红书收藏到 Obsidian""小红书收藏批量抓取"时使用。适用场景：用户不想装浏览器自动化、C 盘空间紧张、要进 Obsidian 知识库逐个学习整理。
---

# 小红书收藏 → Obsidian 导出流水线（纯 Python 无浏览器）

## 何时用
- 用户要把小红书**自己的收藏**整理进 Obsidian（逐个学习/分类），但**不想装浏览器/Chromium**、空间紧张。
- 不要用于爬取他人内容、评论、私页——仅本人收藏。

## 核心架构（4 层）
1. **登录态**：从已登录浏览器取 `web_session` + `a1`（一次性，约 1 年有效）。不下载任何东西。
2. **签名**：纯 Python `xhshow` 库（`pip install xhshow`）本地算 `x-s/x-t/x-s-common`，**无需浏览器/JS 运行时**。
3. **请求**：`curl_cffi`（Chrome 131 指纹 impersonate）发 HTTP——**不能**用 `requests`，会被 Shield 按 JA3 指纹拉黑返回 461/412。
4. **导出**：枚举收藏 → 图文取详情+图片转 webp 本地化；视频仅存元数据 → 写 Obsidian MD（YAML frontmatter + `![[...]]` 嵌入）。

## 关键接口（已验证，非臆测）
- **取自己 user_id**：`GET https://edith.xiaohongshu.com/api/sns/web/v2/user/me`，带签名+cookie，返回 `data.user_id`。
- **枚举收藏**：`GET https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page`
  - query: `num=30&cursor=<上页cursor>&image_formats=webp&user_id=<uid>`
  - 响应数据在 **`data.notes`**（不是 items/cards）；翻页用 `data.has_more` + `data.cursor`。
  - 每条 `type`：`normal`=图文，`video`=视频。
- **笔记详情（图文取正文/图片用）**：**`POST https://edith.xiaohongshu.com/api/sns/web/v1/feed`**
  - body（JSON）：`{"source_note_id": <id>, "xsec_token": <token>, "xsec_source": "pc_feed", "image_formats": "webp"}`
  - ⚠️ 字段是 **`source_note_id`** 不是 `note_id`；用 GET `/v2/note/{id}` 会 404。
  - 返回 `data.note`：`desc`(正文)、`image_list`(`info_list[].url` 取 webp)、`tag_list`、`interact_info`(liked_count/collected_count)。
  - 签名用 xhshow 的 **`sign_headers_post`**（不是 sign_headers_get）。
- 每条收藏的 `xsec_token` 从 `data.notes[].xsec_token` 拿，调详情时必传。

## Cookie 处理（踩坑点）
- `web_session` 是 **httpOnly**，DevTools Console 的 `document.cookie` 取不到 → 必须走 DevTools→Application→Cookies 面板，或 Cookie-Editor 扩展，或本地解密脚本（见下）。
- **请求必须显式把 web_session/a1 写进 Cookie 头**，且 domain 设 `.xiaohongshu.com`（否则发不到 edith 子域）。
- **curl_cffi cookie 冲突**：`acw_tc` 在 www/edith 两域各一份会报 "Multiple cookies exist with name=acw_tc"。修复：每次请求**显式传 `cookies=ck` dict** + 请求后 `s.cookies.clear()`，以 ck 为唯一来源；ck 含 web_session/a1/webId，从响应刷新 acw_tc。
- 设备指纹稳定：首页 `GET https://www.xiaohongshu.com` 初始化一次拿 `webId/gid`，整会话复用，别每次重置。

## 风控（必做，否则封号/限流）
- 单线程；随机延迟 **2–5 秒**（不是固定间隔，去机械性）。
- 滑动窗口 **≤20 次/分**（远低于 100/分触发线）。
- cursor **顺序**翻页，不跳页、不并发。
- 本人住宅 IP + 本人收藏 → 风险低（最糟是限流/滑块，非封号）。
- 遇 `412/461/300012` 指数退避，连败 3 次暂停。
- `state.json` 存 cursor + 已导出 id 支持**断点续传**。

## 输出格式（Obsidian 友好）
- 图文 MD：`status: unstudied` / `category: 待分类` / `resourceId` / `author` / `link` / `tags` / `liked_count` / `collected_count` / `xsec_token`；正文 + `![[images/xxx.webp]]`。
- 视频 MD：仅 `title/link/author/type/status` + 说明"按需求仅存元数据不下载视频"。
- 图片转 **webp**（默认 1080 宽，C 盘紧可降 720），用 `![[...]]` 内联。
- 生成 `index.md` 总索引（每条一行链接）。
- 配合 Obsidian + Dataview 按 `status` 建"待学/已学"看板。

## 分组（零 LLM 配置）
- 脚本只做抓取+写文件，**不接 AI**。
- 分组由 **WorkBuddy 当前对话窗口 AI** 读 MD 后做语义归类、回填 `category/tags`——用户无需自己配任何模型。

## 依赖与运行
```
python -m venv .venv && .venv/Scripts/pip install curl_cffi xhshow
python exporter.py            # 全量
python exporter.py --limit 10 # 限量验证
```
- 若取 cookie 想零手动：装 `pywin32`，读 Edge 加密 Cookie 库（`%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies`）用 `win32crypt.CryptUnprotectData` 本地解密。**注意 Edge 运行时锁文件**（WinError 32）——需关闭 Edge 全部进程或手动复制。

## 已知限制
- 签名是逆向产物，小红书约每月轮换算法，`xhshow` 失效时跟其升级即可。
- 调用私有 API 违反 XHS ToS，风险自担。
- 本地解密 Cookie 脚本涉及本机凭证，仅本机运行、不落库外传。
