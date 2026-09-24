# 小红书 → Obsidian 导出工具 SPEC V2.0

> 版本：v2.0（升级稿，待评审）
> 前身：v0.4（精简版，已实现并开源：纯 Python 零浏览器导出收藏）
> 开源仓库：https://github.com/FrankChen668/xhs-favorites-to-obsidian
> 定位升级：**从"单一收藏导出器"升级为"可配置、可插拔采集的多能力导出框架"**

---

## 1. 目标与定位

| 维度 | V1.0 | V2.0 |
|---|---|---|
| 能力范围 | 仅"我的收藏" | 收藏 + 搜索 + 发现页 + 关注流 + 指定用户笔记（可开关） |
| 频率/限速 | 写死（20 次/分 + 2–5s） | **配置驱动**，按场景可调 |
| 视频处理 | 写死"仅链接" | **可选**：仅链接 / 下载 mp4 |
| 自动分组 | 独立脚本，必跑 | **可选开关**，可跳过 |
| 图片处理 | 写死 1080/webp/82 | **可配置** 格式/尺寸/质量/跳过 |
| 使用门槛 | 改代码才能改行为 | 改 `config.yaml` 或加 CLI flag 即可 |

**G1** 零浏览器、零 Chromium —— 纯 Python（`curl_cffi` 指纹 + `xhshow` 纯 Python 签名），签名本地算。
**G2** 采集能力**可插拔**：所有能力共享同一传输/签名层，新增能力只需加一个 Collector 类。
**G3** 行为**完全可配置**：频率、媒体策略、后处理全部由配置或 CLI 决定，默认值安全但可覆盖。
**G4** 输出保持 Obsidian 原生 Markdown（frontmatter + 图片 `![[...]]`），可选视频下载。

---

## 2. 设计原则

- **P1 传输与业务解耦**：`XHSClient`（签名/限速/重试/熔断）与各个 `Collector`（业务接口）分离。新增能力不动传输层。
- **P2 配置优于硬编码**：任何"可能因用户/场景变化的量"都进配置，禁止在代码里写死默认值（除非是安全兜底下限）。
- **P3 可选即跳过**：每个后处理步骤（分类、索引、看板）独立开关，关掉则零开销。
- **P4 安全默认值**：默认配置落在"低风险安全带"（≤25 次/分、单线程、顺序翻页），用户主动调高才放开。
- **P5 断点续传不变**：`state.json` 记录每个采集器的游标，中断可续。

---

## 3. 架构（V2 核心：可插拔采集器）

```
xhs2obsidian/
├── src/
│   ├── client.py          # XHSClient：curl_cffi + xhshow 签名 + RateLimiter + 重试/熔断
│   ├── collectors/
│   │   ├── base.py        # Collector 抽象：fetch_page() / parse()
│   │   ├── favorites.py   # 收藏（已验证 ✅）
│   │   ├── search.py      # 关键词搜索（需验证端点参数）
│   │   ├── explore.py     # 发现页 / 关注流（需验证）
│   │   └── user_notes.py  # 指定用户笔记（需验证）
│   ├── media.py           # 图片转 webp + 视频下载（按配置分支）
│   ├── exporter.py        # 写 Obsidian MD + frontmatter + 索引（V1 已有，重构接入配置）
│   ├── classify.py        # 自动分组（可选后处理，V1 已有）
│   ├── config.py          # 读取/校验 config.yaml + CLI 覆盖
│   └── main.py            # 入口：按配置装配 collectors → 调度 → 后处理
├── config.example.yaml
└── secrets/cookies.json   # gitignore，本地凭证
```

**关键抽象**：所有 Collector 实现统一接口，返回标准化 `NoteRecord`（id、type、title、author、desc、image_list、video_url、xsec_token…）。`exporter` / `media` / `classify` 只认 `NoteRecord`，不关心来源——这就是"收藏之外能力"能低成本接入的原因。

---

## 4. 配置项（V2 核心交付物）

> 以下为 `config.yaml` 完整 Schema。**所有项均可被 CLI flag 覆盖**（如 `--rate-limit.requests-per-min 15`、`--collectors.search.enabled true --collectors.search.keywords "AI Agent"`）。

```yaml
# === 凭证 ===
cookie_file: secrets/cookies.json      # 必须含 web_session + a1 + user_id

# === 输出 ===
output_dir: ./vault                     # Obsidian vault 目录或子目录
index_file: index.md                    # 总索引文件名（空字符串=不生成）

# === 传输层 / 风控（全部可调）===
rate_limit:
  requests_per_min: 20                   # 滑动窗口上限。安全带 10–25，超过自担风险
  min_delay: 2.0                         # 随机延迟下限(秒)，去机械性
  max_delay: 5.0                         # 随机延迟上限(秒)
  concurrency: 1                         # 并发（默认 1；>1 风险显著上升）
  backoff:
    max_retries: 3                       # 遇风控码重试次数
    base_seconds: 10                     # 指数退避基数
    trigger_codes: [412, 461, 300012]    # 触发退避的返回码
  circuit_breaker:                       # 连败熔断，防账号风险
    fail_threshold: 3                    # 连续失败 N 次
    pause_minutes: 15                    # 自动暂停时长

# === 采集器（可插拔、可独立开关）===
collectors:
  favorites:
    enabled: true                        # V1 已验证 ✅
    num_per_page: 30
  search:
    enabled: false                       # 需验证端点参数
    keywords: []                         # 例: ["AI Agent", "Obsidian 技巧"]
    max_pages: 5                         # 0=不限（直到无更多）
    sort: general                        # general | latest | most_comment | most_like
  explore:
    enabled: false                       # 需验证端点参数
    channel: recommend                   # recommend(推荐) | following(关注)
    max_pages: 5
  user_notes:
    enabled: false                       # 需验证端点参数
    target_user_id: ""                   # 指定用户 id

# === 媒体处理（视频可选项 + 图片可配置）===
media:
  images:
    enabled: true
    format: webp                         # webp | jpg | keep(原格式)
    max_width: 1080                      # 720 更省空间
    quality: 82
    skip_if_no_text: false               # true=纯图无文字也下载图片
  video:
    mode: link_only                      # link_only(仅标题+链接) | download(下载 mp4)
    download_dir: videos
    max_size_mb: 500                     # 超过则跳过下载，仅留链接
    expire_buffer_min: 30                # CDN 签名 URL 到期前缓冲，防下载途中失效

# === 后处理（全部可选）===
post_process:
  auto_classify: true                    # 拉取后自动分组打标签（写 category/tags）
  regenerate_index: true                 # 重新生成 index.md（按分类分组）
  dataview_board: false                  # 额外生成 Dataview 看板 md（status 看板）

# === 运行态 ===
resume: true                             # state.json 断点续传
log_level: INFO                          # DEBUG | INFO | WARNING
```

---

## 5. 能力矩阵（含实现状态与风险）

| 能力 | 端点 | 实现状态 | 难度 | 说明 |
|---|---|---|---|---|
| 收藏 | `GET /v2/note/collect/page` | ✅ 已验证 | 低 | 数据在 `data.notes`，需 `user_id` |
| 笔记详情 | `POST /v1/feed` (`source_note_id`+`xsec_token`) | ✅ 已验证 | 低 | 图文取正文+图片，视频取元数据 |
| 搜索 | `GET /v1/search/notes` | ⚠️ 实现中（端点待实测确认） | 低 | 参数 `keyword/page/search_id/sort` 需实测 |
| 发现页 | `GET /v1/feed` (channel=recommend) | ⚠️ 实现中 | 中 | 信息流分页 |
| 关注流 | 独立端点（待逆向确认） | ⚠️ 实现中 | 中 | "关注"tab 端点待确认 |
| 指定用户笔记/动态 | `GET /v1/user/posted` 或 `/v2/user/notes` | ⚠️ 实现中 | 中 | 需 `target_user_id`（单用户） |

> 诚实声明：V2 把全部能力列为**在 scope 内必做**。收藏/详情已实测跑通；其余 4 项端点在实现阶段逐一对拍（如同 V1 发现 `feed` 是 POST 那样实测修正）。**不保证签名后一定可用**——小红书接口会调整，验证失败的端点将标注为"暂不可用"而非硬塞。

---

## 6. 命令行接口（草案）

```bash
# 默认：按 config.yaml 跑全部 enabled 采集器
python src/main.py

# 仅收藏，限速降到 15 次/分，不下载图片
python src/main.py --collectors.favorites.enabled true \
  --rate-limit.requests-per-min 15 --media.images.enabled false

# 跑搜索（临时覆盖配置，不改动 yaml）
python src/main.py --collectors.search.enabled true \
  --collectors.search.keywords "AI Agent" "Obsidian" --collectors.favorites.enabled false

# 视频改为下载模式
python src/main.py --media.video.mode download --media.video.max-size-mb 300

# 跳过所有后处理（只要原始导出）
python src/main.py --post-process.auto-classify false --post-process.regenerate-index false
```

---

## 7. 合规与风控（继承 V1，随配置升级）

- **平台 ToS**：调用私有 API 抓取本身违反 XHS 条款，与用哪个能力无关，使用者自担风险。
- **频率边界**：默认 ≤25 次/分；超过由用户主动配置，工具仅作提醒。
- **本人场景最安全**：读自己收藏/关注属最温和一类；搜索/发现页属公开内容，风险相当。
- **数据本地**：全程本地，不外传任何数据；`cookies.json` 必须 gitignore。
- **不内置 LLM**：自动分组用确定性关键词打分（V1 已验证覆盖 98%），AI 语义分组仍交 WorkBuddy 窗口，**脚本零 LLM 依赖**。

---

## 8. V1 → V2 升级路线（实现阶段才执行，仅规划）

1. **抽取 `client.py`**：把 V1 `exporter.py` 里的 `signed_get/signed_post`、cookie 管理、`RateLimiter` 抽成独立 `XHSClient`，限速参数全部来自配置。
2. **抽象 `Collector`**：`favorites` 先行迁移为第一个 Collector；`search/explore/user_notes` 在验证端点后逐个补。
3. **`media.py` 分支出视频下载**：复用 V1 已有的图片 webp 逻辑，新增 `video.mode=download` 分支（带 CDN 有效期缓冲）。
4. **`config.py` + `main.py`**：统一装配，CLI flag 覆盖配置。
5. **`classify.py` / 索引** 接 `post_process` 开关。
6. 更新 README、SKILL.md、仓库说明，标注哪些能力已验证 / 待验证。

---

## 9. 评审决策记录（已拍板，2026-09-25）

| 问题 | 决策 | 落地到 |
|---|---|---|
| Q1 默认频率 | **沿用 V1**（20 次/分 + 2–5s，`concurrency=1`）；先把功能做扎实，后续再调高 | §4 `rate_limit` 默认值不变 |
| Q2 视频默认 | **继承 V1：`link_only`**；但**实现 `download` 分支并实测 1 个**确认可行性 | §4 `media.video.mode` 默认 `link_only`，另测 1 个下载 |
| Q3 必做范围 | **V2 全做**：收藏 + 搜索 + 发现/关注 + 用户动态/笔记，常见能力都覆盖 | §5 全部 in-scope，§8 全实现 |
| Q4 配置格式 | **纯 `config.yaml` 即可**，不支持环境变量 | 不引入 env 解析 |
| Q5 多用户 | **单用户**（`target_user_id` 单个），避免批量出问题 | `user_notes.target_user_id` 单值 |

> 决策原则：先稳后快、先全后优。默认配置保持 V1 安全阀，新能力先验证端点可达再纳入框架。

---

## 10. 红线（继承并补充）

- **禁止**安装/依赖 Chromium、Playwright、任何浏览器自动化（C1）。
- **禁止**爬取非本人隐私数据（他人私信、未公开主页）——仅限本人收藏/关注 + 公开内容（C3）。
- **禁止**硬编码 cookie 进脚本或提交仓库（C5）。
- **禁止**把签名算法整段抄袭闭源商业插件（C8，参考思路自行实现）。
- **禁止**把默认限速调到 >25 次/分（安全下限，用户明确配置除外）。
- **禁止**在脚本内调用 LLM（C7，AI 分组交 WorkBuddy 窗口）。
