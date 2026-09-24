---
name: xhs-favorites-to-obsidian
description: 纯 Python 零浏览器把小红书收藏/搜索/动态/发现/关注导出为 Obsidian 笔记（可配置、可插拔采集）。当用户想把小红书内容导出到 Obsidian、整理收藏、批量抓取笔记，或问"不装浏览器怎么抓小红书"时使用。
---

# xhs-favorites-to-obsidian

## 何时使用
- 用户想把小红书内容（收藏/搜索/动态/发现/关注）导出成 Obsidian 可读的 Markdown。
- 用户强调**不想装浏览器、不想做浏览器自动化、电脑空间不够**。
- 用户已授权运行脚本（需在 WorkBuddy Agent 模式下，且明确允许执行）。

## 核心约束（务必遵守）
- **零浏览器**：只用 `curl_cffi`（Chrome 指纹）+ `xhshow`（纯 Python 签名）。**绝不**安装 Chromium / Playwright。
- **不爬他人隐私**：仅本人收藏/动态 + 公开内容。
- **Cookie 安全**：存 `secrets/cookies.json`，gitignore 排除，不硬编码、不提交。

## 已验证可用的端点（实测 code=0）
- 收藏：`GET /api/sns/web/v2/note/collect/page`（user_id + cursor）
- 详情：`POST /api/sns/web/v1/feed`（source_note_id + xsec_token）
- 搜索：**POST** `/v1/search/notes`（keyword/page/page_size/search_id/sort/note_type/image_formats）
- 动态：`GET /v1/user_posted`（user_id + num + cursor）
- 发现/推荐：`POST /v1/homefeed`（search_page_request_source=discover_feed）
- 关注流：`POST /v1/homefeed`（search_page_request_source=following）
- 视频地址：详情 `video.media_v2`（JSON 字符串）→ `stream.h264[0].master_url`

## 运行流程
1. 确认有 `secrets/cookies.json`（web_session + a1 + user_id）。没有则 `python src/extract_edge_cookies.py`（需浏览器未锁 Cookie 库）或手动从 DevTools 复制。
2. `cp config.example.yaml config.yaml`，按需改 `output_dir` 与开启的 `collectors`。
3. `python -m src.main`（或带 CLI 覆盖，如 `--collectors.search.enabled true --collectors.search.keywords "AI"`）。
4. 产物在 `output_dir`：每篇一个 `.md`（YAML frontmatter + 正文 + `![[图片]]`），`index.md` 按分类分组，图片在 `images/`，视频在 `videos/`。

## 关键解析注意
- favorites / user_posted：note_id、xsec_token、display_title、type、user 直接在 item 顶层。
- search / homefeed：顶层 `id`=note_id、`xsec_token` 顶层；正文在 `note_card` 内；homefeed 的 note_card **无 image_list**，需调详情拿图。
- 视频：详情里 `video.media_v2` 是 JSON 字符串，`stream.h264[0].master_url` 才是播放地址。

## 风控默认（安全）
- 20 次/分 + 随机 2–5s + 单线程 + 顺序翻页 + 固定指纹 + 断点续传。可调高但需用户明确授权。

## 风险提示
- 调用私有 API 违反 XHS ToS；签名约每月轮换（升级 `xhshow` 即可）。
- 视频下载较大，默认 `link_only`；下载模式需用户明确开启。
