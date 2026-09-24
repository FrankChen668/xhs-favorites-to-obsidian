---
tags: xhs-dataview
---

# 小红书导出 · Obsidian 看板（Dataview）

> 用法：把本文件复制到你的 Obsidian vault 内（与导出的笔记同级或按需调整 `FROM` 路径），
> 安装 **Dataview** 插件即可渲染下方查询为实时看板。
> 导出工具的 `output_dir` 默认指向 `F:/Obsidian/小红书`，故下方 `FROM "小红书"` 对应 vault 内的 `小红书` 文件夹。
> 若你的笔记在其他位置，把 `"小红书"` 改成实际文件夹名即可。

## 1. 待学清单（按收藏数降序，优先高赞）

```dataview
TABLE category AS 分类, type AS 类型, author AS 作者, liked_count AS 赞, collected_count AS 收藏
FROM "小红书"
WHERE status = "unstudied"
SORT collected_count DESC, file.ctime DESC
```

## 2. 学习中 / 已学

```dataview
TABLE category AS 分类, review_date AS 复习日, author AS 作者
FROM "小红书"
WHERE status != "unstudied"
SORT review_date DESC
```

## 3. 分类分布看板

```dataview
TABLE length(rows) AS 篇数
FROM "小红书"
GROUP BY category
SORT length(rows) DESC
```

## 4. 视频笔记（默认仅元数据，点链接观看）

```dataview
TABLE author AS 作者, duration AS 时长, link AS 链接
FROM "小红书"
WHERE type = "video"
SORT file.ctime DESC
```

## 5. 按标签筛选（示例：AI 技术类）

```dataview
TABLE category AS 分类, author AS 作者, link AS 链接
FROM "小红书"
WHERE contains(tags, "Agent") OR contains(tags, "RAG") OR contains(tags, "MCP")
SORT collected_count DESC
```

## 6. 按分类下钻（示例：把某一类单独成表）

```dataview
TABLE type AS 类型, author AS 作者, collected_count AS 收藏, link AS 链接
FROM "小红书"
WHERE category = "AI技术工程"
SORT collected_count DESC
```

---

### 字段说明（来自导出 frontmatter）
- `status`：`unstudied`（待学）/ `studying`（学习中）/ `done`（已学）。学完一篇改 `status: done` 并填 `review_date: "YYYY-MM-DD"`。
- `category`：自动分类结果（AI技术工程 / AI产品PM / 旅行攻略 / 穿搭 / 美食 / 效率与知识管理 …），未命中为 `待分类` / `未分类`。
- `tags`：分类命中的关键词标签数组。
- `type`：`normal`（图文）/ `video`（视频）。
- `collected_count` / `liked_count`：收藏 / 点赞数（字符串，Dataview 排序时可用 `number(collected_count)` 强制数值排序）。

> 提示：若想严格按数值排序，把 `SORT collected_count DESC` 改为 `SORT number(collected_count) DESC`。
