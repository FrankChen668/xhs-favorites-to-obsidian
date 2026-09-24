# xhs-favorites-to-obsidian

纯 Python、零浏览器（不装 Chromium / 不跑自动化）把**小红书**内容导出为 **Obsidian** 笔记的命令行工具。

> V2.0：从"单一收藏导出器"升级为**可配置、可插拔采集的多能力框架**——收藏 / 搜索 / 动态 / 发现 / 关注，全部可选、全部可配。

## 特性

- **零浏览器**：用 `curl_cffi`（Chrome 指纹）发请求 + `xhshow`（纯 Python 逆向签名）算 `x-s/x-t/x-s-common`，签名在本地算，**不安装任何浏览器或 JS 运行时**。
- **多采集能力**（可独立开关）：
  - `favorites` 我的收藏 ✅ 已验证
  - `search` 关键词搜索 ✅ 已验证
  - `user_notes` 我的动态/笔记 ✅ 已验证
  - `explore` 发现/推荐流 ✅ 已验证
  - `following` 关注流 ✅ 已验证
- **完全可配置**：频率、媒体策略、后处理全部由 `config.yaml` 或 CLI 决定，默认值安全（≤25 次/分、单线程）。
- **视频可选**：`link_only`（仅标题+链接，默认）或 `download`（下载 mp4，已验证可行）。
- **自动分组**：确定性关键词打分，把笔记按主题（AI/旅行/穿搭…）归类、回填 `category/tags`，并生成分类索引。
- **断点续传**：`state.json` 记录已导出条目，中断可续。
- **数据本地**：全程本地，不外传；`secrets/` 已被 `.gitignore` 排除。

## 安装

```bash
python -m venv venv && venv/Scripts/python -m pip install -r requirements.txt
```

依赖：`curl_cffi`、`xhshow`、`pyyaml`、`pillow`。

## 获取 Cookie

两种方式（任选其一）：

1. **自动脚本**（需本机 Edge/Chrome 关闭或允许读其加密 Cookie 库）：
   ```bash
   python src/extract_edge_cookies.py      # 自动抽出 web_session + a1 写入 secrets/cookies.json
   ```
   > 注意：若 Edge/Chrome 正在运行并锁住 Cookie 数据库，脚本会失败，需先完全退出浏览器进程。
2. **手动**：Edge/Chrome 打开 xiaohongshu.com 并登录 → F12 → 应用程序 → Cookies → `https://www.xiaohongshu.com` → 复制 `web_session`（httpOnly，Application 面板才能取到）和 `a1` → 写入：
   ```json
   {"web_session": "xxx", "a1": "yyy", "user_id": "你的user_id"}
   ```
   `user_id` 可留空，工具首次运行会从接口补全；也可手动填（见下方"获取 user_id"）。

## 配置

复制示例并修改：

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml：至少确认 output_dir、按需开启 collectors
```

## 使用

```bash
# 默认：按 config.yaml 跑全部 enabled 采集器（默认仅 favorites）
python -m src.main

# 仅收藏，限速降到 15 次/分，不下载图片
python -m src.main --rate-limit.requests-per-min 15 --media.images.enabled false

# 跑搜索（临时覆盖，不改动 yaml）
python -m src.main --collectors.search.enabled true --collectors.search.keywords "AI Agent" "Obsidian" --collectors.favorites.enabled false

# 视频改为下载模式
python -m src.main --media.video.mode download --media.video.max-size-mb 300

# 跳过所有后处理（只要原始导出）
python -m src.main --post_process.auto-classify false --post_process.regenerate-index false
```

所有配置项均支持 `--点分.路径 值` 覆盖（见 `config.example.yaml`）。

## 在 Obsidian 中使用

把 `output_dir` 指向你的 vault 子目录（或直接就是 vault），Obsidian 打开即是标准 Markdown。
- 笔记含 `status: unstudied`（待学）/ `studying` / `done`，适合"逐个学习"追踪；
- 装 **Dataview** 插件后，可用 `status` 字段做"待学 → 已学"看板；学完一篇改 `status: done` 并填 `review_date`。
- 仓库根目录 [`dataview-board.md`](./dataview-board.md) 是一份现成的看板模板（待学清单 / 分类分布 / 视频笔记 / 按标签筛选 / 按分类下钻），复制到 vault 并把 `FROM "小红书"` 改成你的实际文件夹即可用。

## 合规与风控

- 调用小红书私有 API 抓取**违反其平台 ToS**，使用者需自担风险。
- 默认 ≤25 次/分、单线程、顺序翻页、随机延迟、固定设备指纹、本人住宅 IP——属低频个人使用，风险低非零；最糟后果是限流/重登/滑块，非封号。
- 仅处理**本人收藏/动态**与**公开内容**；不爬取他人隐私数据。
- 签名算法来自社区逆向（`xhshow`），约每月轮换，失效后 `pip install -U xhshow` 升级即可。
- 本项目为学习/个人备份用途，请勿大规模搬运或二次发布他人内容。

## 项目结构

```
src/
  client.py             # 传输层：签名 + 限速 + 重试/退避 + 熔断 + cookie
  config.py             # 配置加载与 CLI 覆盖
  collectors/           # 可插拔采集器（favorites/search/user_notes/feed）
  media.py              # 图片转 webp + 视频下载
  exporter.py           # 写 Obsidian MD + frontmatter
  classify.py           # 自动分组打标签
  extract_edge_cookies.py  # 本机浏览器 Cookie 自动提取
  main.py               # 入口
dev/                   # 开发/调试用脚本（端点验证探针，非运行必需）
  probe_endpoints.py / probe_struct.py
```

## License

MIT
