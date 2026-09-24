#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 F:/Obsidian/小红书 下所有收藏 MD 做分类与打标签（确定性、可复现）。
- 读取每个 MD 的 frontmatter（category / tags）
- 基于标题关键词打分，选出 top1 分类 + 提取 tags
- 回写 frontmatter，并重新生成带「分类」列的 index.md
仅改 frontmatter 两行，不动正文。
"""
import os, re, glob

BASE = r"F:/Obsidian/小红书"

# 分类关键词表（读完全部 587 条标题后归纳）。打分=命中关键词数，取最高分类。
CATS = {
    "AI技术工程": ["agent","llm","大模型","multi-agent","多agent","rag","向量","知识库","ontology",
        "本体","transformer","微调","推理","记忆系统","graph","loop","harness","prompt","mcp",
        "编码","代码","编程","vibe coding","codex","github","架构","模型","神经网络","深度学习",
        "监督","智能体","token","api","cli","agent team","agent实践","agent评估","agent故障",
        "agent记忆","agent面试","agent图工程","loop工程","graph工程","数据治理","智能问数","本体论",
        "ai","人工智能","程序员","护城河","langchain","claude","claude code","课程","id生成",
        "复刻","屎山","pua","开源了","爆火","开源项目","梗","流水线","gpt-6","重构","提示词","vibecoding",
        "知识付费","完全开源","ai圈","技术文章","自学","技术团队","ai native","演讲","红杉","闭门会",
        "gpt","chatgpt","gemini","vibe code"],
    "AI产品PM": ["产品经理","pm","prd","原型","需求","产品方法论","用户访谈","市场洞察","解决方案顾问",
        "求职","offer","面试","jd","简历","交付","ai产品经理","平台pm","产品进阶","业务范围",
        "工作流","产品需求","需求文档","prd需求","ai时代","ai人才","重复工作","赚钱","演讲","产品人",
        "作业帮","跨行","找工作","最会用","外包","解决方案","最优","团队","规则","这碗饭","能力","fde"],
    "AI做PPT与Skill": ["ppt","skill","模板","排版","图表","杂志","咨询","麦肯锡","html","毕业照",
        "海报","设计风格","pptx","ai ppt","可编辑","动态","流程图","绘图","手绘","mermaid","drawio",
        "设计ui","ppt技巧","ppt大纲","ppt网页","ppt模板","ppt恐惧症","ppt代码","ppt工作流","magic",
        "chatgpt","gemini","gpt image","老照片","玩法","插画","风格","改字","ps","长视频","短视频",
        "转场","科普动画","文档","截图","教程","口头禅","立个规矩"],
    "学术科研": ["科研","论文","综述","学术","国自然","文献","答辩","盲审","毕业季","毕业论文",
        "科研狗","科研绘图","sci","导师"],
    "旅行攻略": ["旅游","攻略","新疆","伊犁","洛阳","郑州","泗阳","江苏","新加坡","深圳","汕头","南澳",
        "西安","台州","三门峡","合肥","安徽","顺德","柳州","香港","石河子","北疆","自驾","漂流","团建",
        "徒步","秘境","草原","赛里木湖","小环线","海岛","出行","出游","景点","美食特种兵","跨年","春节",
        "端午","国庆","县城生活","宿迁","大美宿迁","南澳岛","广州南","云南","甘肃","青海","商丘",
        "张家港","常州","军垦","玛纳斯","水库","疯狂动物城","火车","打卡","头等舱","途中的","好体验"],
    "婚嫁备孕": ["订婚","结婚","婚纱照","婚纱","备孕","孕妇","准爸爸","三金","五金","金条","金手镯",
        "领证","答谢宴","婚礼","接亲","纪念日","登记照","备婚","养育","带娃","约会","场所","孕妈妈","控糖","水果"],
    "穿搭配饰": ["鞋","洞洞鞋","老爹鞋","项链","红宝石","祖母绿","桃花","皮带","衬衫","t恤","中山装",
        "上衣","防晒衣","穿搭","质感","西装","长袖","短袖","配享太庙","穿出","工装","牛仔","华夫格",
        "立领","老爹","梦中情鞋","鞋控","百搭","戒指","钻石","万宝龙","教授","穿的","高知","通勤包"],
    "美食": ["美食","吃什么","小吃","炸串","拉面","烧饼","早餐","火锅","酸汤","糯米鸭","餐厅","特产",
        "必买","越南","京东超市","碳水","凉拌","好吃","宝藏小馆","苍蝇小馆","泗阳美食","江苏人吃什么",
        "顺德","大卢饼","油条","菜市场","美食分享","广东胃","家乡美食","东莞","吃了","蒸菜","菜角","宵夜","吃宵夜"],
    "效率与知识管理": ["obsidian","知识管理","笔记","学习方法","费曼","第二大脑","时间管理","待办","效率",
        "提效","自动化","摸鱼","副业","头像","微信名","打工","自律","作息","读书","管理","领导力","管人",
        "拜年","职场","sql","mysql","excel","word","手写","打印机","数据可视化","背单词","盲打","神器",
        "网站","宝藏","工作流程","学习项目","信息源","技能清单","斜杠","上班","下班","累","书","系列",
        "上网","学习","陌生领域","插件","快捷指令","会议","英文","纪要","屏幕","记录自己","脑科学","记不住","读完","本书"],
    "运动健康生活": ["游泳","蛙泳","仰泳","自由泳","跑步","半马","网球","反手","自行车","皮卡丘","乡村生活",
        "拍照姿势","晒被子","健康","脑梗","疾病","鼻塞","医学","养生","健身","羽毛球","运动","医生","小狗","冲浪"],
    "数码与其他": ["索尼","耳机","华为","折叠屏","电池","锂电池","储能","产业链","域名","ai味","丑设计",
        "设计","毕业","论文","科研","天气","潮牌","非遗","租房","地铁","火车站","机场","高铁","江苏特产",
        "特产合集","高铁站","西九龙","樟宜","挂钩","追剧","抖音","屏蔽词","父母","礼物","母亲节","翠屏",
        "送礼","办事","拍照","人像","童年","江南春","生猪","东大"],
}

# 每个分类下可提取为 tag 的代表词（更细）
TAG_WORDS = {
    "AI技术工程": ["Agent","LLM","RAG","Codex","MCP","Graph","架构","记忆系统","向量库","提示词","VibeCoding"],
    "AI产品PM": ["产品经理","PRD","原型","求职","面试","用户研究","解决方案"],
    "AI做PPT与Skill": ["PPT","Skill","HTML","麦肯锡风","可编辑","设计"],
    "学术科研": ["科研","论文","综述","国自然"],
    "旅行攻略": ["旅行","攻略","自驾","漂流","城市游","小众秘境"],
    "婚嫁备孕": ["订婚","结婚","婚纱","备孕","三金五金","领证"],
    "穿搭配饰": ["鞋履","项链","上衣","衬衫","穿搭","配饰"],
    "美食": ["美食","小吃","家乡味","餐厅"],
    "效率与知识管理": ["知识管理","Obsidian","效率","副业","职场","工具网站","SQL"],
    "运动健康生活": ["游泳","跑步","运动","健康","乡村"],
    "数码与其他": ["数码","储能","产业链","租房","交通","设计"],
}

def classify(title):
    t = title.lower()
    scores = {}
    for cat, kws in CATS.items():
        s = 0
        for kw in kws:
            if kw.lower() in t:
                s += 1
        if s > 0:
            scores[cat] = s
    if not scores:
        return "未分类", []
    # 取最高分；并列时按 CATS 定义顺序（更具体的优先靠后定义会被先匹配？这里取首个最高）
    best = max(scores, key=lambda c: (scores[c], -list(CATS).index(c)))
    tags = []
    for w in TAG_WORDS.get(best, []):
        if w.lower() in t or any(kw.lower() in t for kw in CATS[best] if w.lower() in kw.lower()):
            tags.append(w)
    # 补充：从标题里抓到该分类的代表词就作为 tag
    extra = []
    for cat, kws in CATS.items():
        if cat == best:
            for kw in kws:
                # 仅取长度>=2且为显式主题词
                if len(kw) >= 2 and kw.lower() in t and kw.lower() not in [x.lower() for x in extra]:
                    # 映射到可读 tag
                    pass
    return best, tags[:4]

def update_frontmatter(path, category, tags):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if not (lines and lines[0].strip() == "---"):
        return False
    # 找 frontmatter 区间
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return False
    out = []
    replaced_cat = False
    replaced_tags = False
    for i in range(1, end):
        line = lines[i]
        if re.match(r"^category\s*:", line) and not replaced_cat:
            out.append(f"category: {category}")
            replaced_cat = True
        elif re.match(r"^tags\s*:", line) and not replaced_tags:
            tagstr = "[" + ", ".join(tags) + "]" if tags else "[]"
            out.append(f"tags: {tagstr}")
            replaced_tags = True
        else:
            out.append(line)
    if not replaced_cat:
        out.append(f"category: {category}")
    if not replaced_tags:
        out.append("tags: []")
    new_lines = lines[:1] + out + lines[end:]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
    return True

def main():
    files = glob.glob(os.path.join(BASE, "*.md"))
    files = [f for f in files if os.path.basename(f) != "index.md"]
    dist = {}
    total = 0
    samples = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            txt = fh.read()
        m = re.search(r"^title:\s*(.+)$", txt, re.MULTILINE)
        title = m.group(1).strip().strip('"') if m else os.path.basename(f)
        cat, tags = classify(title)
        ok = update_frontmatter(f, cat, tags)
        dist[cat] = dist.get(cat, 0) + 1
        total += 1
        if len(samples) < 3:
            samples.append((title[:30], cat, tags))
    # 输出分布
    print(f"[*] 已分类 {total} 篇")
    print("[*] 分类分布：")
    for cat, n in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {n}")
    # 重新生成 index.md（带分类列）
    regen_index()

def regen_index():
    files = glob.glob(os.path.join(BASE, "*.md"))
    files = [f for f in files if os.path.basename(f) != "index.md"]
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            txt = fh.read()
        d = {}
        for key in ["title","type","author","category","tags","link","resourceId"]:
            m = re.search(rf"^{key}:\s*(.+)$", txt, re.MULTILINE)
            d[key] = m.group(1).strip().strip('"') if m else ""
        base = os.path.splitext(os.path.basename(f))[0]
        rows.append(d)
    # 按分类分组
    from collections import defaultdict
    groups = defaultdict(list)
    for d in rows:
        groups[d.get("category","未分类")].append(d)
    lines = ["---", "tags: xhs-favorites-index", "---", "# 小红书收藏索引（已分类）", "",
             f"总数：{len(rows)}", ""]
    for cat in sorted(groups, key=lambda c: -len(groups[c])):
        lines.append(f"## {cat}（{len(groups[cat])}）")
        lines.append("")
        lines.append("| 类型 | 分类 | 标题 | 标签 |")
        lines.append("| --- | --- | --- | --- |")
        for d in groups[cat]:
            t = d.get("type","")
            title = d.get("title","")
            tags = d.get("tags","")
            link = d.get("link","")
            lines.append(f"| {t} | {cat} | [{title}]({link}) | {tags} |")
        lines.append("")
    with open(os.path.join(BASE, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[*] index.md 已重新生成（{len(rows)} 篇，按分类分组）")

if __name__ == "__main__":
    main()
