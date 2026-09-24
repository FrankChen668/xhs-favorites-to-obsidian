# xhs-favorites-to-obsidian

纯 Python、零浏览器（无 Chromium / Playwright）把**你自己的小红书收藏夹**（图文 + 视频）导出为 Obsidian 可用的 Markdown 笔记，并自动按标题做分类打标签。

- 不装浏览器、不跑无头引擎、不模拟翻收藏页 —— 签名在本地用纯 Python 计算。
- 视频笔记按需求**只存元数据**（标题 / 链接 / 作者），不下载视频文件。
- 图文笔记取正文 + 图片（webp）本地化，用 `![[...]]` 内联，Obsidian 直接可读可学。
- 自带断点续传、限速风控、自动分类。

> ⚠️ **合规声明**：小红书**没有官方开放收藏读取 API**，本项目调用的是平台私有 Web 接口，仅用于**个人备份与学习整理**自己的收藏，请遵守平台 ToS，勿用于批量爬取他人内容或商业用途。签名算法为社区逆向成果，平台改动后可能失效，届时升级 `xhshow` 即可。

## 工作原理

| 环节 | 做法 |
|---|---|
| 登录态 | 从已登录的浏览器取 `web_session` + `a1`（一次性，约 1 年有效），不下载任何东西 |
| 签名 | `xhshow` 纯 Python 本地算 `x-s/x-t/x-s-common`，无需浏览器 / JS 运行时 |
| 请求 | `curl_cffi`（Chrome 指纹 impersonate）发 HTTP —— **不能**用 `requests`，会被 Shield 按 JA3 指纹拉黑 |
| 导出 | 枚举收藏 → 图文取详情 + 图片转 webp；视频仅元数据 → 写 Obsidian MD |

### 关键接口（已验证）
- 取自己的 `user_id`：`GET /api/sns/web/v2/user/me`
- 枚举收藏：`GET /api/sns/web/v2/note/collect/page`（`user_id` + `cursor` 翻页，数据在 `data.notes`）
- 笔记详情（图文取正文/图片）：**`POST /api/sns/web/v1/feed`**，body 用 `source_note_id` + `xsec_token`

## 安装

```bash
git clone https://github.com/FrankChen668/xhs-favorites-to-obsidian.git
cd xhs-favorites-to-obsidian
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp config.example.yaml config.yaml   # 填写你的 output_dir
```

## 获取 Cookie（三种方式）

1. **自动提取（Windows，推荐）**：装 `pywin32` 后运行 `python src/extract_edge_cookies.py`，它会读取本机 Edge 加密 Cookie 库并本地解密，自动写出 `secrets/cookies.json`（**不外传**）。
2. **DevTools 手动**：Edge 打开 xiaohongshu.com 并登录 → F12 → 应用程序 → Cookies → `https://www.xiaohongshu.com` → 复制 `web_session`（httpOnly，Console 取不到）和 `a1`。
3. **Cookie-Editor 扩展**：装扩展 → Export JSON → 取出 `web_session` / `a1`。

> `web_session` 是 httpOnly，必须走面板 / 扩展 / 自动脚本，不能用 `document.cookie`。

把值写进 `secrets/cookies.json`：
```json
{ "web_session": "xxxx", "a1": "yyyy", "user_id": "你的user_id(可选，脚本会自动取)" }
```

## 使用

```bash
# 连通性探针（只读一页，不动收藏）
python src/probe.py

# 全量导出
python src/exporter.py

# 限量验证（前 10 条）
python src/exporter.py --limit 10

# 按标题自动分类 + 打标签，并重建带「分类」列的 index.md
python src/classify.py
```

导出目录结构：
```
<output_dir>/
  ├── 笔记标题_resourceId.md      # 图文：正文 + ![[images/xxx.webp]]
  ├── 视频标题_resourceId.md      # 视频：仅元数据
  ├── images/                     # 图片 webp 本地化
  └── index.md                    # 按分类分组的索引
```

每篇笔记 frontmatter 含 `status: unstudied` / `category` / `tags` / `xsec_token`，配合 Obsidian + Dataview 即可做「待学 / 已学」看板。

## 风控（务必保留）
- 单线程 + 随机 2–5s 间隔 + 滑动窗口 ≤20 次/分（远低于 100/分触发线）。
- cursor 顺序翻页、不并发、不跳页。
- 本人住宅 IP + 本人收藏 → 风险低（最糟是限流 / 滑块，非封号）。
- `state.json` 支持中断后续传。

## 能力拓展（不仅限于收藏）
签名层是通用的：任何 XHS 私有接口都能用 `xhshow` 签名后调用，因此本方案可横向拓展：
- **搜索**：`GET /api/sns/web/v1/search/notes?keyword=...`
- **发现 / 热点**：`GET /api/sns/web/v1/feed`（发现页流）
- **关注流 / 用户主页**：对应用户动态 / 关注接口

这些端点需要进一步逆向参数，欢迎 PR。

## 许可证
[MIT](LICENSE)
