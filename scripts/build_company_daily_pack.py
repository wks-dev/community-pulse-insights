#!/usr/bin/env python3
"""Build a compact company/market daily Web AI prompt pack."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from load_game_list import read_spreadsheet


AI_TOOLS: dict[str, dict[str, Any]] = {
    "元宝": {
        "slug": "yuanbao",
        "url": "https://yuanbao.tencent.com/chat/naQivTmsDa",
        "entry_url": "https://yuanbao.tencent.com/chat/naQivTmsDa",
        "entry_mode": "direct",
        "platform_focus": "微信生态、公众号、新闻、腾讯系内容、中文网页",
    },
    "豆包": {
        "slug": "doubao",
        "url": "https://www.doubao.com/chat/?channel=browser_landing_page",
        "entry_url": "https://www.doubao.com/chat/?channel=browser_landing_page",
        "entry_mode": "direct",
        "platform_focus": "抖音、微博、B站、中文网页、新闻、TikTok线索",
    },
    "文心一言": {
        "slug": "wenxin",
        "url": "https://wenxin.baidu.com/",
        "entry_url": "https://wenxin.baidu.com/",
        "entry_mode": "direct",
        "platform_focus": "百度、中文网页、新闻、贴吧、百度知道/百科生态",
    },
    "千问": {
        "slug": "qianwen",
        "url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_mode": "direct",
        "platform_focus": "中文网页、新闻、公开搜索、跨平台社区线索；千问只是执行工具，不是检索对象",
    },
    "点点": {
        "slug": "diandian",
        "url": "https://www.xiaohongshu.com/ai_chat",
        "entry_url": "https://www.xiaohongshu.com/",
        "entry_mode": "open_xiaohongshu_then_ai_chat",
        "platform_focus": "小红书、种草内容、女性向讨论、社媒讨论；优先返回 xiaohongshu.com 或 xhslink.com 证据",
    },
    "知乎直答": {
        "slug": "zhida",
        "url": "https://zhida.zhihu.com/",
        "entry_url": "https://zhida.zhihu.com/",
        "entry_mode": "direct",
        "platform_focus": "知乎问答、争议复盘、中文网页",
    },
    "Gemini": {
        "slug": "gemini",
        "url": "https://gemini.google.com/app",
        "entry_url": "https://gemini.google.com/app",
        "entry_mode": "direct",
        "platform_focus": "全球公开网页、YouTube、Instagram、海外社区",
    },
    "Grok": {
        "slug": "grok",
        "url": "https://grok.com/",
        "entry_url": "https://grok.com/",
        "entry_mode": "direct",
        "platform_focus": "X/Twitter、全球社媒、实时公开讨论",
    },
}

DEFAULT_TOOLS = ["元宝", "豆包", "文心一言", "千问", "点点", "知乎直答", "Gemini", "Grok"]
DEFAULT_COMMUNITY_DEEP_DIVE_TOOLS = ["点点", "知乎直答"]
DEFAULT_WEEKLY_EXPANSION_TOOLS = ["豆包", "Gemini", "Grok"]
ROBUST_FALLBACK_TOOLS = {"千问", "Grok", "Gemini", "点点", "知乎直答", "文心一言"}
GROUPED_SHORT_FRAGILE_TOOLS = {"豆包", "点点", "知乎直答", "千问", "文心一言", "元宝"}

GROUPED_SHORT_GROUPS: list[dict[str, Any]] = [
    {
        "group_id": "group_core_mihoyo_kuro",
        "group_name": "核心米哈游 / 库洛运营与社区反馈",
        "target_platform_role": "米哈游与库洛核心运营产品、版本节奏、角色/剧情/抽卡/回流退坑反馈",
        "keywords": [
            "米哈游", "mihoyo", "hoyoverse", "原神", "genshin", "绝区零", "zenless", "zzz",
            "星穹铁道", "star rail", "hsr", "崩坏3", "honkai impact", "鸣潮", "wuthering", "wuwa",
            "战双", "punishing", "pgr", "库洛", "kuro",
            "幻塔", "tower of fantasy", "深空之眼", "尘白", "snowbreak", "七大罪", "女神异闻录", "persona",
        ],
    },
    {
        "group_id": "group_cn_competitor_ops",
        "group_name": "国内二游竞品运营与社区事件",
        "target_platform_role": "国内二游竞品、长期运营、版本争议、抽卡付费、玩家留存和社区节奏",
        "keywords": [
            "明日方舟", "arknights", "阴阳师", "onmyoji", "碧蓝航线", "azur",
            "少前", "少女前线", "girls", "fgo", "命运冠位指定", "幻塔", "tower of fantasy",
            "重返未来", "1999", "白荆回廊", "尘白禁区",
        ],
    },
    {
        "group_id": "group_new_product_watch",
        "group_name": "新品测试 / 预约 / 赛道观察",
        "target_platform_role": "新品测试、预约、爆料、PV、首测反馈、开放世界/搜打撤/宠物养成等赛道信号",
        "keywords": [
            "因缘精灵", "nexus anima", "星布谷地", "petit planet", "varsapura", "雨之城",
            "蓝色星原", "azure promilia", "无限大", "ananta", "异环", "neverness",
            "二重螺旋", "duet night", "望月", "新月同行",
            "伊莫", "归环", "project nami", "project sun", "测试", "预约", "首测",
        ],
    },
    {
        "group_id": "group_sector_female_lifestyle",
        "group_name": "女性向 / 生活方式 / 小红书讨论",
        "target_platform_role": "女性向、恋爱向、角色消费、剧情口碑、小红书种草、生活方式与泛二游情绪",
        "keywords": [
            "恋与深空", "love and deepspace", "恋与制作人", "love and producer", "未定事件簿",
            "tears of themis", "光与夜", "light and night", "暖暖", "nikki", "闪耀暖暖",
            "无限暖暖", "闪耀吧", "噗咪", "赛马娘", "pretty derby", "动物森友会", "animal crossing",
            "心动小镇", "dokev", "creatures of ava", "山海奇旅", "粒粒", "卡蕾多", "白银之城",
            "女性向", "乙女", "小红书", "种草", "生活方式",
        ],
    },
]

PRODUCTS: list[dict[str, str]] = [
    {
        "company": "米哈游",
        "game_name": "FlyMe2theMoon",
        "aliases": "FlyMe2theMoon",
        "product_tier": "history_context",
        "game_status": "早期独立游戏，历史产品",
    },
    {
        "company": "米哈游",
        "game_name": "崩坏学园",
        "aliases": "Zombiegal Kawaii; Houkai Gakuen",
        "product_tier": "history_context",
        "game_status": "早期历史产品",
    },
    {
        "company": "米哈游",
        "game_name": "崩坏学园2",
        "aliases": "Houkai Gakuen 2",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "崩坏3",
        "aliases": "Honkai Impact 3rd",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "未定事件簿",
        "aliases": "Tears of Themis",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "原神",
        "aliases": "Genshin Impact",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "崩坏：星穹铁道",
        "aliases": "Honkai: Star Rail; HSR",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "绝区零",
        "aliases": "Zenless Zone Zero; ZZZ",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "米哈游",
        "game_name": "崩坏：因缘精灵",
        "aliases": "Honkai: Nexus Anima",
        "product_tier": "research_watch",
        "game_status": "正在进行“进化测试”",
    },
    {
        "company": "米哈游",
        "game_name": "星布谷地",
        "aliases": "Petit Planet",
        "product_tier": "research_watch",
        "game_status": "已完成多轮封闭测试，继续研发和预约",
    },
    {
        "company": "米哈游",
        "game_name": "Varsapura",
        "aliases": "雨之城",
        "product_tier": "research_watch",
        "game_status": "已开启首轮保密测试招募",
    },
    {
        "company": "库洛",
        "game_name": "鸣潮",
        "aliases": "Wuthering Waves; WuWa",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
    {
        "company": "库洛",
        "game_name": "战双帕弥什",
        "aliases": "Punishing: Gray Raven; PGR",
        "product_tier": "daily_focus",
        "game_status": "已上线、持续运营",
    },
]

GAME_CATEGORY_LENSES: list[dict[str, str]] = [
    {
        "name": "米哈游新增赛道观察",
        "focus": "休闲种田/类动森、宠物养成",
        "why": "用于观察星布谷地、因缘精灵等新方向的竞品变化、玩家期待、玩法反馈和商业化风险。",
    },
    {
        "name": "库洛潜在方向观察",
        "focus": "搜打撤/撤离射击类、动作竞技、硬核战斗向",
        "why": "用于观察库洛潜在新品方向、硬核动作用户偏好、战斗体验反馈和竞品机会。",
    },
    {
        "name": "双方共同关注方向",
        "focus": "3A 化、开放世界、高品质内容生产、跨端体验",
        "why": "用于观察米哈游与库洛都可能关心的高品质内容投入、跨端体验、工业化能力和玩家预期变化。",
    },
]


def default_product_watch_games() -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    for index, item in enumerate(PRODUCTS, start=1):
        aliases = [item["game_name"]]
        aliases.extend(alias.strip() for alias in item.get("aliases", "").split(";") if alias.strip())
        games.append(
            {
                "game_id": f"default_product_{index:03d}",
                "game_name": item["game_name"],
                "aliases": aliases,
                "source_sheet": "default_company_focus_matrix",
                "company": item.get("company", ""),
                "product_tier": item.get("product_tier", ""),
                "game_status": item.get("game_status", ""),
            }
        )
    return games


def game_search_text(game: dict[str, Any]) -> str:
    values = [game.get("game_name", ""), game.get("company", ""), game.get("product_tier", ""), game.get("game_status", "")]
    values.extend(game.get("aliases") or [])
    return " ".join(str(value or "") for value in values).casefold()


def grouped_short_group_for(game: dict[str, Any]) -> str:
    haystack = game_search_text(game)
    priority = [
        "group_core_mihoyo_kuro",
        "group_new_product_watch",
        "group_sector_female_lifestyle",
        "group_cn_competitor_ops",
    ]
    groups_by_id = {str(group["group_id"]): group for group in GROUPED_SHORT_GROUPS}
    for group_id in priority:
        group = groups_by_id[group_id]
        if any(str(keyword).casefold() in haystack for keyword in group.get("keywords", [])):
            return str(group["group_id"])
    return "group_cn_competitor_ops"


def build_grouped_watch_games(watch_games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_games = watch_games or default_product_watch_games()
    groups = [{key: value for key, value in group.items() if key != "keywords"} | {"games": []} for group in GROUPED_SHORT_GROUPS]
    by_id = {str(group["group_id"]): group for group in groups}
    for game in source_games:
        preferred_id = grouped_short_group_for(game)
        target = by_id.get(preferred_id)
        if target is None:
            target = by_id["group_cn_competitor_ops"]
        target["games"].append(game)
    return groups


def selected_grouped_watch_games(watch_games: list[dict[str, Any]], selected_group_ids: set[str]) -> list[dict[str, Any]]:
    groups = build_grouped_watch_games(watch_games)
    if not selected_group_ids:
        return groups
    return [group for group in groups if str(group.get("group_id")) in selected_group_ids]


def grouped_game_lines(games: list[dict[str, Any]]) -> str:
    if not games:
        return "- 本组暂无游戏；请补充关注矩阵。"
    lines: list[str] = []
    for index, game in enumerate(games, start=1):
        aliases = " / ".join(str(alias) for alias in game.get("aliases", []) if str(alias).strip())
        lines.append(f"{index}. {game.get('game_name', '')} | aliases: {aliases}")
    return "\n".join(lines)


def wrap_grouped_prompt(prompt_id: str, prompt: str) -> str:
    return f"PROMPT_ID={prompt_id}\n{prompt.strip()}"


def grouped_tool_prompt_style(ai_tool: str) -> str:
    if ai_tool == "Grok":
        return "short_numbered_supplement"
    if ai_tool == "Gemini":
        return "medium_grouped_scan"
    if ai_tool in GROUPED_SHORT_FRAGILE_TOOLS:
        return "short_fragile_platform_scan"
    return "short_grouped_scan"


def build_grouped_short_prompt(
    ai_tool: str,
    group: dict[str, Any],
    start_date: str,
    end_date: str,
    lookback_days: int,
) -> str:
    info = AI_TOOLS[ai_tool]
    games = group.get("games") or []
    target_count = "5-8" if ai_tool != "点点" else "4-7"
    style = grouped_tool_prompt_style(ai_tool)
    format_note = "请用编号列表返回，不要输出长 JSON schema。"
    if ai_tool == "Gemini":
        format_note = "可以用短 Markdown 表格或编号列表返回，但不要输出长 JSON schema。"
    if ai_tool == "Grok":
        format_note = "请用 short numbered supplement 返回，每条都是 key:value，不要发送或复述长 JSON schema。"
    if ai_tool == "文心一言":
        format_note = "请只做中文公开网页/百度生态可见线索摘要；如果拒答或只有合规说明，请直接说明无可用结果。"
    if ai_tool == "点点":
        format_note = "请优先小红书/点点语境，URL 没有就写 no_url，并说明待核验。"
    if ai_tool == "知乎直答":
        format_note = "请优先知乎问答/专栏/中文公开网页，URL 没有就写 no_url，并说明待核验。"
    if ai_tool == "千问":
        format_note = "请只检索游戏/社区/新闻目标，不要介绍千问、Qwen、API、下载、PPT、AI生图等工具页。"
    return f"""你是游戏行业社区舆情检索助手。请忽略历史对话，只完成本轮分组短检索。
当前 AI 工具：{ai_tool}
工具覆盖重点：{info['platform_focus']}
检索窗口：最近 {lookback_days} 天，{start_date} 至 {end_date}。
分组 ID：{group['group_id']}
分组名称：{group['group_name']}
平台角色：{group['target_platform_role']}
提示词风格：{style}

本组关注游戏（约 {len(games)} 款）：
{grouped_game_lines(games)}

任务目标：
1. 只从本组游戏及其别名中找最近 {lookback_days} 天有具体事件、社区讨论、版本变化、争议、玩家反馈、测试/预约/PV 或可核验线索的项目。
2. 每个短 prompt 目标返回 {target_count} 条；没有足够结果时少写，不要编。
3. 不强制完美 JSON；{format_note}
4. 每条必须包含：游戏名、事件/标题、平台、玩家反馈、URL 或 no_url、为什么值得关注。
5. 没有真实 URL 的内容只能写 pending_lead / auxiliary_sample，不得写 core_evidence。
6. 不要把 AI 工具产品页、API 页、下载页、PPT/生图/翻译/代码工具区、输入框提示、历史记录当作回答。

建议输出格式：
1. 游戏名: 
   标题或事件: 
   平台: 
   玩家具体意见: 
   为什么值得关注: 
   业务使用: 
   URL: 真实 URL 或 no_url
   evidence_level: core_evidence / auxiliary_sample / pending_lead
   风险等级: low / medium / high
   limitations: 样本限制或待核验说明

硬性边界：
- 不要编造链接、发布时间、帖子标题或玩家原话。
- 如果只有搜索片段或无 URL，URL 字段写 no_url，并在 limitations 说明。
- 如果页面只返回 prompt 回显、工具壳、历史记录或拒答，请直接说明 answer_not_captured，不要伪造线索。
"""


def date_window(end_date: str, lookback_days: int) -> tuple[str, str]:
    end = date.fromisoformat(end_date)
    start = end - timedelta(days=max(lookback_days, 1) - 1)
    return start.isoformat(), end.isoformat()


def product_lines(company: str) -> str:
    rows = [item for item in PRODUCTS if item["company"] == company]
    return "\n".join(
        f"- {item['game_name']} | aliases: {item['aliases']} | tier: {item['product_tier']} | status: {item['game_status']}"
        for item in rows
    )


def load_watch_games(game_list: str | None) -> list[dict[str, Any]]:
    if not game_list:
        return []
    records = read_spreadsheet(Path(game_list))
    watch_games: list[dict[str, Any]] = []
    for record in records:
        aliases = [str(item).strip() for item in record.get("aliases", []) if str(item).strip()]
        if not aliases:
            continue
        watch_games.append(
            {
                "game_id": record.get("game_id", f"watch_{len(watch_games) + 1:03d}"),
                "game_name": str(record.get("game_name") or aliases[0]).strip(),
                "aliases": aliases,
                "source_sheet": record.get("source_sheet", ""),
            }
        )
    return watch_games


def game_category_lens_section() -> str:
    lines = ["游戏类型观察口径："]
    for item in GAME_CATEGORY_LENSES:
        lines.append(f"- {item['name']}：{item['focus']}。用途：{item['why']}")
    return "\n".join(lines)


def watch_game_lines(watch_games: list[dict[str, Any]]) -> str:
    if not watch_games:
        return "- 未接入外部关注矩阵；只使用上方米哈游/库洛产品矩阵。"
    lines = []
    for idx, game in enumerate(watch_games, start=1):
        aliases = " / ".join(str(alias) for alias in game.get("aliases", []) if str(alias).strip())
        lines.append(f"{idx}. {game.get('game_name', '')} | aliases: {aliases}")
    return "\n".join(lines)


def watch_matrix_section(watch_games: list[dict[str, Any]]) -> str:
    return f"""扩展关注/竞品游戏矩阵（只作为观察范围，不生成逐个轮询任务）：
关注游戏数：{len(watch_games)}
{watch_game_lines(watch_games)}

使用规则：
1. 这些游戏用于帮助发现竞品、赛道和大盘信号，不要求逐个返回。
2. 只返回最近 3 天内有实际公开信息、社区讨论、版本变化、争议、玩家反馈或可核验线索的命中项。
3. 没有具体事件、没有明确讨论、没有最近 3 天信息的游戏不要硬写，也不要为了覆盖名单而补空泛描述。
4. 每个命中项必须说明发生了什么、玩家具体怎么说、为什么值得关注、可以拿去和客户/业务聊什么。"""


WEEKLY_SECTOR_LENSES: list[dict[str, str]] = [
    {
        "sector": "休闲种田/类动森",
        "scope": "米哈游新增赛道观察，也可引用任意公开二游/泛游戏案例。",
        "signals": "生活模拟、种田建造、岛屿/家园、慢节奏长期养成、UGC/社交摆放、Animal Crossing/Stardew-like 讨论。",
    },
    {
        "sector": "宠物养成/陪伴养成",
        "scope": "米哈游因缘精灵方向观察，也可引用任意宠物收集、陪伴、自动战斗、轻策略养成案例。",
        "signals": "宠物捕捉、情感陪伴、收集培养、棋盘/自动战斗、陪伴式付费与玩家审美反馈。",
    },
    {
        "sector": "搜打撤/撤离射击",
        "scope": "库洛潜在方向观察，也可引用任意撤离射击、二游化射击、PvPvE、装备带出案例。",
        "signals": "高压力对局、撤离收益、装备损失、反外挂、手游化门槛、女性/二游玩家接受度。",
    },
    {
        "sector": "动作竞技/硬核战斗",
        "scope": "库洛优势方向观察，也可引用动作竞技、Boss挑战、连招深度、硬核反馈案例。",
        "signals": "手感、闪避/弹反、角色强度、Boss机制、竞速排行、难度争议、操作门槛。",
    },
    {
        "sector": "开放世界/3A化/高品质内容生产",
        "scope": "米哈游和库洛共同关注方向，也可引用全球开放世界、跨端、高规格内容案例。",
        "signals": "大版本地图、演出质量、跨端体验、主机/PC/移动同步、内容产能、全球化传播。",
    },
]


def weekly_expansion_section(report_mode: str, watch_games: list[dict[str, Any]]) -> str:
    horizon = "周报" if report_mode == "weekly" else "日报"
    target_total = "12-20" if report_mode == "weekly" else "8-14"
    watch_target = "5-8" if report_mode == "weekly" and watch_games else "2-5"
    non_key_target = "至少 5 条" if report_mode == "weekly" else "至少 2 条"
    sector_lines = "\n".join(
        f"- {item['sector']}：{item['scope']} 重点看：{item['signals']}"
        for item in WEEKLY_SECTOR_LENSES
    )
    return f"""
【{horizon}扩容要求】
1. 本轮是{horizon}观察，不是只围绕米哈游/库洛少量产品写摘要。请尽量返回 {target_total} 条候选内容；如果该平台确实找不到这么多，必须在 limitations 里说明。
2. 关注矩阵不是逐个轮询队列，但要主动扫 44 款关注/竞品游戏的别名。若有证据，尽量命中 {watch_target} 款关注矩阵游戏；没有最近信息的游戏不要硬写，可放入 not_hit_games 简述“不命中原因”。
3. 必须补充“其他二游与竞品动态”：{non_key_target}，优先从关注矩阵或近期公开讨论中选择，不限米哈游/库洛。
4. 必须补充“赛道新闻与案例”，不要只解释赛道定义。任意公司或任意游戏均可，只要能服务这些业务观察方向：
{sector_lines}
5. 每条赛道案例都要填写 sector，并说明它对应哪个观察方向；如果不是具体游戏，也要写清楚行业事件或平台讨论是什么。
6. 每个平台的返回不能只列游戏名，必须给 plain_summary、specific_player_opinions、why_watch、business_use、url/evidence_level/risk_level。
7. URL-less 内容只能是 auxiliary_sample 或 pending_lead；没有 URL 的内容可以增加信息量，但不能写成核心证据。
"""


def json_contract(ai_tool: str, start_date: str, end_date: str, lookback_days: int, report_mode: str = "daily") -> str:
    contract = {
        "ai_tool": ai_tool,
        "report_mode": report_mode,
        "report_window": {
            "start_date": start_date,
            "end_date": end_date,
            "lookback_days": lookback_days,
        },
        "evidence": [
            {
                "company": "米哈游",
                "category": "米哈游新增赛道观察 | 库洛潜在方向观察 | 双方共同关注方向 | 二游大盘 | 其他竞品",
                "sector": "休闲种田/类动森 | 宠物养成/陪伴养成 | 搜打撤/撤离射击 | 动作竞技/硬核战斗 | 开放世界/3A化/高品质内容生产 | none",
                "sector_item": True,
                "is_watch_matrix_game": True,
                "is_key_company": True,
                "game_name": "原神",
                "matched_alias": "Genshin Impact",
                "product_tier": "daily_focus",
                "game_status": "已上线、持续运营",
                "scope": "game",
                "platform": "B站",
                "source_ai": ai_tool,
                "title": "帖子/视频/问答/新闻/公告标题",
                "url": "https://...",
                "published_at": "YYYY-MM-DD 或可核查的相对时间",
                "event_type": "版本",
                "player_tendency": "观望",
                "sentiment": "mixed",
                "risk_level": "medium",
                "summary": "只基于证据的一句话说明",
                "plain_summary": "这件事是什么，用大白话说明，不要写概念化黑话。",
                "specific_player_opinions": "玩家对剧情、角色、玩法、优化、付费或运营的具体意见",
                "why_watch": "为什么今天值得关注",
                "business_use": "可以拿去和客户或内部业务聊什么；如果不能形成业务谈资，请写“不建议外部使用”。",
                "evidence_level": "core_evidence | auxiliary_sample | pending_lead",
                "access_status": "accessible | search_snippet_only | blocked_login | forbidden_403 | captcha | paywalled | no_url | unknown",
                "limitations": "样本限制",
            }
        ],
        "pending_leads": [
            {
                "company": "库洛",
                "game_name": "鸣潮",
                "lead": "无URL、待验证或访问受限的线索",
                "reason": "no_url | blocked | needs_verification",
            }
        ],
        "not_hit_games": [
            {
                "game_name": "关注矩阵中的游戏名",
                "matched_alias": "本轮尝试过的别名",
                "not_hit_reason": "本周期没有找到具体公开信息/社区讨论，未写入证据",
            }
        ],
        "expanded_keywords": ["关键词"],
    }
    return json.dumps(contract, ensure_ascii=False, indent=2)


def tool_identity_guard(ai_tool: str) -> str:
    if ai_tool == "文心一言":
        return f"""工具身份防漂移：
1. “当前 Web AI 工具：{ai_tool}”只表示本轮提交问题的平台，不是检索对象。
2. 禁止把 AI 工具官网、产品介绍页、API 服务页或下载页当成游戏舆情来源。
3. 本轮唯一检索对象是下方列出的公司、游戏、别名和二游大盘主题。
4. 文心一言只做中文公开网页、百度生态、新闻、贴吧、知道、百科和可公开检索样本的观察；遇到与游戏舆情无关的合规提醒时，只记录平台限制并停止该条。"""
    return f"""工具身份防漂移：
1. “当前 Web AI 工具：{ai_tool}”只表示本轮提交问题的平台，不是检索对象。
2. 禁止把任何 AI 工具官网、产品介绍页、API 服务页或下载页当成游戏舆情来源，包括千问、Qwen、通义千问、阿里 AI 助手、豆包、元宝、文心一言、Gemini 和 Grok。
3. 本轮唯一检索对象是下方列出的公司、游戏、别名和二游大盘主题。"""


def build_prompt(
    ai_tool: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
    report_mode: str,
    max_mihoyo: int,
    max_kuro: int,
    max_market: int,
    watch_games: list[dict[str, Any]],
) -> str:
    info = AI_TOOLS[ai_tool]
    category_lenses = game_category_lens_section()
    watch_matrix = watch_matrix_section(watch_games)
    expansion = weekly_expansion_section(report_mode, watch_games)
    point_note = ""
    if ai_tool == "点点":
        point_note = """
点点/小红书专项要求：
1. 必须优先检索小红书语境中的公开内容。
2. 优先返回 xiaohongshu.com 或 xhslink.com 的可核查笔记、搜索结果或话题链接。
3. 没有 URL 的小红书观点只能放入 pending_leads。
"""
    if ai_tool == "知乎直答":
        point_note = """
知乎直答专项要求：
1. 优先检索知乎问题、回答、专栏、争议复盘与中文网页。
2. 不要在知识库订阅页面中生成结论；只使用普通搜索/提问可返回的公开链接。
"""
    if ai_tool == "文心一言":
        point_note = """
文心一言专项要求：
1. 入口应为 https://wenxin.baidu.com/ 的普通文字对话。
2. 优先覆盖百度、贴吧、新闻、中文网页、百度知道/百科生态。
3. 本轮只检索中文公开网页和百度生态样本；不要扩展到与游戏舆情无关的工具、教程或访问方式话题。
4. 不要把合规提醒当作舆情结果；如果系统误判或拒答，请记录为 platform_status，并换用“中文公开网页 + 游戏名/公司名”的短 prompt 重试一次。
5. 不要误入魔法图片、写作帮手、放心写等专项工具。
"""
    if ai_tool == "千问":
        point_note = """
千问专项要求：
1. 入口应为 https://www.qianwen.com/ 的普通文字对话页。
2. 千问只是本轮使用的 AI 工具，不是检索目标；不要检索或总结“千问”“Qwen”“通义千问”“阿里 AI 助手”官网、本页面、API 服务或下载页。
3. 本轮检索目标只能是下方米哈游产品矩阵、库洛产品矩阵、二游大盘的公司名、游戏名、别名和主题。
4. 建议先用这些组合启动检索：米哈游 原神 星穹铁道 绝区零 最近3天 舆情；库洛 鸣潮 战双帕弥什 最近3天 玩家反馈；二游 抽卡 版本 争议 玩家建议。
5. 如果结果只返回千问/通义/Qwen/阿里 AI 助手产品介绍，视为检索漂移：不要写入 evidence 或 pending_leads，必须换用游戏名/公司名重新检索。
6. 不要误入 API 服务、下载电脑端、PPT创作、AI生图、AI生视频、翻译、代码等专项工具。
7. 如果只返回模型概括而没有可核查 URL，必须放入 pending_leads，不得进入 evidence。
"""
    return f"""你是游戏行业社区舆情检索助手。请检索最近 {lookback_days} 天的公开可核查信息，时间窗口为 {start_date} 至 {end_date}，截止日期为 {end_date}。

当前 Web AI 工具：{ai_tool}
该工具重点覆盖：{info['platform_focus']}
{tool_identity_guard(ai_tool)}
{point_note}

{category_lenses}

{watch_matrix}

{expansion}

本次任务是第一层“公司/大盘快扫”。请做得足够详细，但不要写成散文。目标是快速发现值得日报追踪的事件、帖子、评论区趋势和玩家倾向。
请只返回有证据价值的内容，并严格遵守“没有 URL 不进入 evidence”的规则。
请注意：扩展关注/竞品游戏矩阵不是逐个轮询清单。你不需要逐个回答每款游戏是否有消息，只需要返回最近 {lookback_days} 天确实有公开信息、社区讨论、版本变化、争议、玩家反馈或可核验线索的命中项。回复量不能只有游戏名，必须包含具体事件和玩家/业务解释。

一、米哈游产品矩阵
{product_lines('米哈游')}

米哈游最多返回 {max_mihoyo} 条。请重点找：
- 最近版本、角色、活动、卡池、剧情、玩法、优化、福利、运营争议。
- 玩家入坑、回流、退坑、抽卡、付费、观望倾向。
- 对剧情、角色、玩法、优化、付费或运营的具体意见。
- 崩坏：因缘精灵、星布谷地、Varsapura 只有出现公开测试/招募/预约/爆料/讨论证据时才返回。
- FlyMe2theMoon、崩坏学园只在与当前品牌/IP/周年/怀旧/争议相关时返回。

二、库洛产品矩阵
{product_lines('库洛')}

库洛最多返回 {max_kuro} 条。请重点找：
- 鸣潮、战双帕弥什最近版本、角色、活动、战斗体验、剧情、优化、补偿、运营节奏。
- 玩家对库洛与米哈游或其他二游的竞品比较。
- 玩家入坑、回流、退坑、抽卡、付费、观望倾向。

三、二游大盘与其他二游/竞品动态
最多返回 {max_market} 条。请重点找：
- 最近 {lookback_days} 天二游玩家共同关注点、社区争议、版本节奏变化、付费/抽卡争议、女性向/男性向分化、平台传播差异。
- 不限米哈游/库洛，请尽量补充关注矩阵或近期二游里的具体游戏案例，让报告信息量更充足。
- 至少尝试覆盖“赛道新闻与案例”：休闲种田/类动森、宠物养成/陪伴养成、搜打撤/撤离射击、动作竞技/硬核战斗、开放世界/3A化/高品质内容生产。
- 米哈游和库洛相关事件如果影响大盘，也要说明。

四、玩家倾向维度
每条证据都尽量补充以下字段，不要只写“正面/负面”：
- 入坑/回流：是什么内容、福利、角色、版本、口碑或朋友推荐促发。
- 退坑/流失：是什么 BUG、优化、剧情、付费、长草、运营、社区争议促发。
- 抽卡/付费：角色强度、人设、XP、保底、福利、礼包、氪金压力、性价比。
- 观望：等待版本、等待优化、等待口碑、等待竞品表现。
- 具体建议：玩家希望怎么改剧情、角色塑造、玩法循环、优化、活动、付费或沟通。
- 平台差异：小红书偏种草/女性向/角色消费，知乎偏争议复盘，B站偏视频评论，微博偏扩散，NGA/贴吧偏硬核争论，海外平台偏全球玩家反应。

五、命中项字段要求
每个命中项至少返回以下字段：
- game_name：具体游戏名；如果是赛道/大盘趋势才可写二游大盘。
- matched_alias：命中的别名、英文名、日文名或关键词。
- company：可明确归属时写米哈游/库洛；竞品或赛道观察无法归属时写二游大盘或其他竞品，并用 category 说明。
- category：米哈游新增赛道观察 / 库洛潜在方向观察 / 双方共同关注方向 / 二游大盘 / 其他竞品。
- sector：如果是赛道新闻或案例，必须填写上述赛道名；否则写 none。
- sector_item：赛道新闻或案例写 true，否则写 false。
- is_watch_matrix_game：命中关注矩阵游戏写 true，否则写 false。
- is_key_company：米哈游/库洛旗下或公司级事件写 true，其他二游/竞品写 false。
- event_type：社区讨论、版本更新、新闻公告、产品测试、竞品动态、玩家建议、争议风险等。
- title：原始标题或可核验事件标题。
- plain_summary：这件事是什么，用大白话说明，不要写概念化黑话。
- specific_player_opinions：玩家具体怎么说，尽量写清触发点和真实反馈。
- why_watch：为什么今天值得关注。
- business_use：可以拿去和客户或内部业务聊什么；如果不适合外部使用，请明确写“不建议外部使用”。
- url：有真实 URL 就填；没有 URL 必须留空。
- evidence_level：core_evidence / auxiliary_sample / pending_lead。没有 URL 的内容不能写 core_evidence。
- risk_level：low / medium / high。
- limitations：样本限制、访问限制、只看到搜索片段、无 URL 等。

输出必须是严格 JSON，不要在 JSON 前后添加解释文字。格式如下：
{json_contract(ai_tool, start_date, end_date, lookback_days, report_mode)}

硬性要求：
1. 不得编造链接、帖子、新闻、公告、视频、发布时间或玩家原话。
2. evidence 中每条必须有可核查 URL；没有 URL 的内容必须放入 pending_leads。
3. 每个结论必须能由对应 URL 或可见搜索结果片段支持。
4. {('只使用当前页面可见的中文公开内容；无法打开的链接留空，并在 limitations 说明。' if ai_tool == '文心一言' else '遇到登录、验证码、403、付费墙、私密群或访问受限，不得绕过，只能写入 access_status 和 limitations。')}
5. 如果只能看到搜索结果片段，请标记 access_status=search_snippet_only。
6. 不要返回长篇介绍；优先返回最近、风险高、跨平台重复、玩家意向明确、设计可借鉴的内容。
7. company 只能填一个实际值：米哈游、库洛或二游大盘；禁止照抄“米哈游 | 库洛 | 二游大盘”这类占位文本。
8. game_name 只有 scope=market 且内容确实是二游大盘趋势时才能填“二游大盘”；凡是涉及具体游戏，必须填实际游戏名，例如 原神、崩坏：星穹铁道、绝区零、鸣潮、战双帕弥什。
9. 如果检索结果是 AI 工具官网、产品介绍页、API 服务页或下载页，不能把 game_name 写成“二游大盘”，应判定为检索漂移并重新搜索游戏/厂商关键词。
10. 没有具体事件、没有最近 {lookback_days} 天信息、没有明确社区讨论的游戏不要硬写；不要为了覆盖关注矩阵而补空泛内容。
11. URL-less 内容不能作为核心证据，只能进入 pending_leads，或在允许 relaxed sampling 的情况下标为 auxiliary_sample。
12. AI 工具产品页、API 页、下载页、介绍页必须判定为 prompt_drift，不能写成二游大盘，也不能写入 evidence。
"""


def build_community_deep_dive_prompt(
    ai_tool: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
    report_mode: str,
    max_items: int,
    watch_games: list[dict[str, Any]],
) -> str:
    info = AI_TOOLS[ai_tool]
    category_lenses = game_category_lens_section()
    watch_matrix = watch_matrix_section(watch_games)
    expansion = weekly_expansion_section(report_mode, watch_games)
    if ai_tool == "点点":
        platform_scope = "小红书/点点"
        community_focus = """
请把自己当成小红书社区观察员，重点找：
- 女性向、角色厨、CP、剧情党、外观/美术、种草/避雷、氪金体验、抽卡分享、版本回流/退坑。
- 米哈游：未定事件簿、原神、崩坏：星穹铁道、绝区零、崩坏3，以及研发/测试产品出现小红书讨论时的女性向反馈。
- 库洛：鸣潮、战双帕弥什在角色、剧情、战斗、优化、运营方面的小红书玩家讨论。
- 二游大盘：女性玩家关注点、角色消费、剧情争议、社区情绪、种草/拔草趋势。
优先返回 xiaohongshu.com 或 xhslink.com 链接。没有链接的笔记标题或观点只能放入 pending_leads。
"""
    elif ai_tool == "知乎直答":
        platform_scope = "知乎/知乎直答"
        community_focus = """
请把自己当成知乎争议复盘观察员，重点找：
- 最近 3 天内知乎问题、回答、专栏或中文网页中关于二游的争议、复盘、竞品比较、运营评价。
- 米哈游与库洛的版本节奏、角色设计、剧情评价、付费设计、优化问题、玩家信任。
- 玩家倾向要具体拆成入坑、回流、退坑、抽卡、付费、观望、建议、争议讨论。
- 二游大盘要总结社区讨论背后的原因，不要只列话题名。
优先返回 zhihu.com 或可公开核查的中文网页链接。没有链接的概括只能放入 pending_leads。
"""
    else:
        platform_scope = info["platform_focus"]
        community_focus = "请补充该平台最能反映玩家倾向的公开社区讨论。"

    return f"""你是游戏社区舆情深挖助手。请在最近 {lookback_days} 天内检索公开可核查内容，时间窗口为 {start_date} 至 {end_date}。

本轮是第二层“社区深挖”，目标平台：{platform_scope}
当前 Web AI 工具：{ai_tool}
工具覆盖重点：{info['platform_focus']}
{tool_identity_guard(ai_tool)}

{community_focus}

{category_lenses}

{watch_matrix}

{expansion}

必须覆盖的公司/产品矩阵：
米哈游：
{product_lines('米哈游')}

库洛：
{product_lines('库洛')}

请最多返回 {max_items} 条最能反映玩家倾向的社区证据。优先级：
1. 有具体帖子、回答、视频、评论区或公开搜索结果 URL。
2. 能体现玩家真实倾向：入坑、回流、退坑、抽卡、付费、观望、建议、争议讨论。
3. 能说明玩家为什么这样想，而不只是情绪标签。
4. 能为日报提供“风险预警”或“可借鉴设计点”。
5. 关注矩阵不是逐个轮询清单；只返回最近 {lookback_days} 天确实有社区讨论或公开线索的命中项，不要硬写空泛游戏名单。

输出严格 JSON，不要在 JSON 前后添加解释文字。格式如下：
{json_contract(ai_tool, start_date, end_date, lookback_days, report_mode)}

硬性要求：
1. evidence 中每条必须有可核查 URL；没有 URL 的内容必须放入 pending_leads。
2. 不得编造链接、帖子、发布时间、玩家原话或统计数据。
3. 遇到登录、验证码、403、付费墙、私密群或访问受限，不得绕过，只能写入 access_status 和 limitations。
4. specific_player_opinions 必须尽量写具体，例如“认为剧情节奏拖沓”“角色塑造吸引回流”“抽卡压力导致观望”等。
5. company 只能填一个实际值：米哈游、库洛或二游大盘；game_name 只有真正的大盘趋势才能填“二游大盘”，具体游戏必须填实际游戏名。
6. 每条命中项必须尽量补全 plain_summary、why_watch、business_use、evidence_level；没有 URL 的内容不能写 core_evidence。
"""


def build_weekly_expansion_prompt(
    ai_tool: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
    report_mode: str,
    max_items: int,
    watch_games: list[dict[str, Any]],
) -> str:
    """Build a weekly supplement prompt focused on breadth and sector cases."""
    info = AI_TOOLS[ai_tool]
    watch_matrix = watch_matrix_section(watch_games)
    expansion = weekly_expansion_section(report_mode, watch_games)
    return f"""你是二次元游戏行业周报扩展检索助手。请检索最近 {lookback_days} 天公开可核查信息，时间窗口为 {start_date} 至 {end_date}。
当前 Web AI 工具：{ai_tool}
工具覆盖重点：{info['platform_focus']}
{tool_identity_guard(ai_tool)}

本轮不是补写定义，也不是只围绕米哈游/库洛。你的任务是补足周报的信息量，让报告覆盖更多关注矩阵游戏、其他二游/竞品动态和赛道案例。

{watch_matrix}

{expansion}

请按以下三组返回，合计最多 {max_items} 条：
1. 关注矩阵命中扩展：优先从 40+ 款关注/竞品游戏里找最近 {lookback_days} 天有公开信息或社区讨论的项目，尽量覆盖不同游戏。不要逐个轮询，也不要硬写安静游戏。
2. 其他二游与竞品动态：不限米哈游/库洛，优先写具体游戏、具体事件、具体玩家反馈，避免只写“二游大盘”。
3. 赛道新闻与案例：必须围绕休闲种田/类动森、宠物养成/陪伴养成、搜打撤/撤离射击、动作竞技/硬核战斗、开放世界/3A化/高品质内容生产。任何公司或游戏都可以，只要是最近 {lookback_days} 天可用于业务观察的实际新闻、公告、社区讨论或版本变化。

每条命中项至少要有：
- game_name
- matched_alias
- company 或 category
- sector：不是赛道案例写 none
- sector_item：赛道案例写 true，否则 false
- is_watch_matrix_game
- is_key_company
- event_type
- title
- plain_summary：这件事是什么，用大白话说明
- specific_player_opinions：玩家具体怎么说
- why_watch：为什么值得关注
- business_use：可以拿去跟客户/业务聊什么
- url：有 URL 就填真实 URL；没有 URL 留空
- evidence_level：core_evidence / auxiliary_sample / pending_lead
- risk_level：low / medium / high
- limitations

硬性规则：
1. 没有最近 {lookback_days} 天具体事件、没有明确公开信息、没有明确讨论的游戏不要硬写。
2. URL-less 内容不能作为 core_evidence，只能是 auxiliary_sample 或 pending_lead。
3. AI 工具产品页、API 页、下载页、介绍页必须判定为 prompt_drift，不能写成二游大盘。
4. 优先返回真实 URL 支撑的内容；如果只能看到搜索片段或摘要，写清楚 limitations。
5. 输出必须是严格 JSON，不要在 JSON 前后添加解释文字。格式如下：
{json_contract(ai_tool, start_date, end_date, lookback_days, report_mode)}
"""


def build_short_fallback_prompt(
    ai_tool: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
) -> str:
    """Build a short raw-first fallback prompt for brittle Web AI pages."""
    shared_targets = (
        "米哈游、原神、崩坏：星穹铁道、绝区零、崩坏3、未定事件簿、"
        "库洛、鸣潮、战双帕弥什、二游大盘、抽卡、版本、玩家反馈、争议、回流、退坑、观望"
    )
    if ai_tool == "点点":
        scope = "只检索小红书/点点语境，重点关注女性向、角色消费、剧情争议、抽卡付费、回流退坑、玩家建议。"
        source_hint = "优先给 xiaohongshu.com 或 xhslink.com；没有链接也可以写，但必须标记“待核验”。"
    elif ai_tool == "千问":
        scope = "只检索具体游戏、厂商和玩家社区，不介绍任何 AI 工具。"
        source_hint = "每条尽量提供公开来源链接；只返回有具体游戏事件的内容。"
    elif ai_tool == "文心一言":
        scope = "只检索中文公开网页、百度、贴吧和新闻中的具体游戏事件，不介绍任何 AI 工具。"
        source_hint = "请用编号文本返回，优先提供标题、日期、玩家反馈和公开来源链接；没有可靠内容就明确说没有找到。"
    elif ai_tool == "知乎直答":
        scope = "只检索知乎问题、回答、专栏和中文公开网页中的具体游戏讨论。"
        source_hint = "本轮必须从普通主页新建问题；成功后才算新结果。"
    elif ai_tool == "Grok":
        scope = "优先检索 X/Twitter、海外新闻、YouTube/全球社区对米哈游、库洛和二游大盘的讨论。"
        source_hint = "可以用 Markdown 列表；有 X/新闻/视频链接就直接贴 URL，没有链接则写待核验。"
    elif ai_tool == "Gemini":
        scope = "优先检索全球公开网页、YouTube、海外社区和新闻，不要求长篇解释。"
        source_hint = "如果无法给 JSON，就用短 Markdown 表格返回，但每条要有 URL 或写 no_url。"
    else:
        scope = "检索公开网页与社区讨论。"
        source_hint = "有 URL 就贴 URL；没有 URL 就写待核验。"
    if ai_tool == "文心一言":
        return f"""请只完成本轮游戏行业公开信息检索。
时间窗口：最近 {lookback_days} 天，{start_date} 至 {end_date}，截止 {end_date}。

重点游戏和关键词：
{shared_targets}

检索范围：
{scope}
{source_hint}

请最多返回 10 条最重要内容，按编号输出。每条包含：游戏名、标题、日期、发生了什么、玩家反馈、为什么值得关注、公开来源链接。

不要编造链接、发布时间、帖子标题或玩家原话。"""
    return f"""请忽略历史对话，只完成本轮短提示词 fallback。
时间窗口：最近 {lookback_days} 天，{start_date} 至 {end_date}，截止 {end_date}。
当前 AI 工具：{ai_tool}

检索目标关键词：
{shared_targets}

平台/工具专项：
{scope}
{source_hint}

请最多返回 8 条最重要内容。第一轮目标是 raw 采集，不强制完美 JSON；但请尽量结构化。
每条内容必须包含：
- 公司：米哈游 / 库洛 / 二游大盘
- 游戏名：具体游戏名；只有真正市场趋势才写“二游大盘”
- 标题或事件
- 平台
- 发布时间或时间线索
- 玩家倾向：入坑 / 回流 / 退坑 / 抽卡 / 付费 / 观望 / 建议 / 分化
- 玩家具体意见
- 风险等级：low / medium / high
- URL：真实可核查链接；没有就写 no_url，并说明待核验

不要编造链接、发布时间、帖子标题或玩家原话。"""


def fallback_fields(
    ai_tool: str,
    run_id: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
) -> dict[str, Any]:
    if ai_tool not in ROBUST_FALLBACK_TOOLS:
        return {}
    slug = AI_TOOLS[ai_tool]["slug"]
    fallback_prompt_id = f"{slug}_short_fallback_001"
    fallback_prompt = build_short_fallback_prompt(ai_tool, start_date, end_date, lookback_days)
    if ai_tool in {"文心一言", "千问", "点点", "知乎直答"}:
        # These pages are sensitive to long automation-prefixed prompts. Keep a
        # plain prompt ID for auditability without adding the automation phrase.
        fallback_prompt = f"PROMPT_ID={fallback_prompt_id}\n{fallback_prompt.strip()}"
    else:
        fallback_prompt = prompt_with_automation_marker(fallback_prompt_id, run_id, fallback_prompt)
    return {
        "fallback_policy": "retry_once_after_send_failure_prompt_drift_or_unparsed_raw",
        "fallback_prompt_id": fallback_prompt_id,
        "fallback_raw_output_path": f"raw/{fallback_prompt_id}.json",
        "fallback_prompt": fallback_prompt,
        "fallback_send_contract": {
            "点点": "visible_unique_input_then_scoped_send_then_finished_ai_message",
            "知乎直答": "clean_home_route_then_new_search_route_and_prompt_id",
            "文心一言": "root_page_then_wait_unique_ci_textarea_then_safe_prompt",
            "千问": "ordinary_chat_input_then_full_visible_answer_not_last_prompt_marker",
            "豆包": "textarea_value_confirmation_not_body_text",
            "Gemini": "visible_ql_editor_keyboard_paste_then_current_prompt_answer",
        }.get(ai_tool, "current_prompt_id_and_new_answer"),
    }


def prompt_with_automation_marker(prompt_id: str, run_id: str, prompt: str) -> str:
    marker = (
        "AUTOMATION_MARKER (for browser automation only; do not use as a search keyword): "
        f"COLLECT_RUN_ID={run_id}; PROMPT_ID={prompt_id}"
    )
    return f"{marker}\n\n{prompt.strip()}"


def parse_group_tool_map(value: str) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for chunk in str(value or "").split(";"):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise ValueError(f"Invalid --group-tool-map chunk: {chunk}")
        group_id, raw_tools = chunk.split("=", 1)
        tools = [item.strip() for item in raw_tools.replace(",", "|").split("|") if item.strip()]
        if not tools:
            raise ValueError(f"Empty tool list for group: {group_id}")
        unknown_tools = [tool for tool in tools if tool not in AI_TOOLS]
        if unknown_tools:
            raise ValueError(f"Unknown AI tools in --group-tool-map: {', '.join(unknown_tools)}")
        mapping[group_id.strip()] = tools
    return mapping


def build_grouped_short_pack(
    args: argparse.Namespace,
    start_date: str,
    end_date: str,
    tools: list[str],
    watch_games: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_group_ids = {item.strip() for item in args.groups.split(",") if item.strip()}
    known_group_ids = {str(group["group_id"]) for group in GROUPED_SHORT_GROUPS}
    unknown_group_ids = sorted(selected_group_ids - known_group_ids)
    if unknown_group_ids:
        raise ValueError(f"Unknown grouped-short groups: {', '.join(unknown_group_ids)}")
    groups = selected_grouped_watch_games(watch_games, selected_group_ids)
    group_tool_map = parse_group_tool_map(args.group_tool_map)
    prompts: list[dict[str, Any]] = []
    for group in groups:
        group_tools = group_tool_map.get(str(group["group_id"]), tools)
        game_names = [str(game.get("game_name") or "") for game in group.get("games", []) if str(game.get("game_name") or "").strip()]
        for tool in group_tools:
            slug = AI_TOOLS[tool]["slug"]
            prompt_id = f"{slug}_{group['group_id']}_short_001"
            prompt_text = wrap_grouped_prompt(
                prompt_id,
                build_grouped_short_prompt(tool, group, start_date, end_date, args.lookback_days),
            )
            item = {
                "prompt_id": prompt_id,
                "stage": "grouped_short_scan",
                "collection_strategy": "grouped_short_scan",
                "prompt_variant": grouped_tool_prompt_style(tool),
                "game_id": group["group_id"],
                "game_name": group["group_name"],
                "group_id": group["group_id"],
                "group_name": group["group_name"],
                "game_count": len(game_names),
                "game_names": game_names,
                "target_platform_role": group["target_platform_role"],
                "prompt_length_chars": len(prompt_text),
                "ai_tool": tool,
                "url": AI_TOOLS[tool]["url"],
                "entry_url": AI_TOOLS[tool]["entry_url"],
                "entry_mode": AI_TOOLS[tool]["entry_mode"],
                "platform_focus": AI_TOOLS[tool]["platform_focus"],
                "time_range": f"{start_date}..{end_date}",
                "report_mode": args.report_mode,
                "watch_game_count": len(watch_games),
                "raw_output_path": f"raw/{prompt_id}.json",
                "prompt": prompt_text,
                "fallback_policy": "none_grouped_short_prompt_is_primary",
                "send_contract": "current_prompt_id_then_selector_or_answer_rescue_candidate",
            }
            prompts.append(item)
    return {
        "report_type": "company_grouped_short_scan",
        "report_mode": args.report_mode,
        "collection_strategy": "grouped_short_scan",
        "run_id": args.run_id,
        "created_at": date.today().isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "lookback_days": args.lookback_days,
        "tools": sorted({tool for item in prompts for tool in [str(item.get("ai_tool") or "")] if tool}),
        "prompt_count": len(prompts),
        "community_deep_dive_enabled": False,
        "community_deep_dive_tools": [],
        "weekly_expansion_enabled": False,
        "weekly_expansion_tools": [],
        "group_count": len(groups),
        "groups": [
            {
                "group_id": group["group_id"],
                "group_name": group["group_name"],
                "game_count": len(group.get("games", [])),
                "game_names": [str(game.get("game_name") or "") for game in group.get("games", [])],
                "target_platform_role": group["target_platform_role"],
            }
            for group in groups
        ],
        "game_count": len(PRODUCTS),
        "watch_game_count": len(watch_games),
        "watch_games": watch_games,
        "game_category_lenses": GAME_CATEGORY_LENSES,
        "weekly_sector_lenses": WEEKLY_SECTOR_LENSES,
        "products": PRODUCTS,
        "prompts": prompts,
    }


def build_pack(args: argparse.Namespace) -> dict[str, Any]:
    start_date, end_date = date_window(args.end_date, args.lookback_days)
    tools = [item.strip() for item in args.tools.split(",") if item.strip()]
    group_tool_map = parse_group_tool_map(args.group_tool_map)
    for mapped_tools in group_tool_map.values():
        for tool in mapped_tools:
            if tool not in tools:
                tools.append(tool)
    unknown = [tool for tool in tools if tool not in AI_TOOLS]
    if unknown:
        raise ValueError(f"Unknown AI tools: {', '.join(unknown)}")
    watch_games = load_watch_games(args.game_list)
    if args.collection_strategy == "grouped_short_scan":
        return build_grouped_short_pack(args, start_date, end_date, tools, watch_games)

    prompts: list[dict[str, Any]] = []
    for tool in tools:
        slug = AI_TOOLS[tool]["slug"]
        prompt_id = f"{slug}_company_daily_001"
        item = {
                "prompt_id": prompt_id,
                "stage": "layer1_fast_scan",
                "game_id": "company_daily",
                "game_name": "多目标日报快扫",
                "ai_tool": tool,
                "url": AI_TOOLS[tool]["url"],
                "entry_url": AI_TOOLS[tool]["entry_url"],
                "entry_mode": AI_TOOLS[tool]["entry_mode"],
                "platform_focus": AI_TOOLS[tool]["platform_focus"],
                "time_range": f"{start_date}..{end_date}",
                "report_mode": args.report_mode,
                "watch_game_count": len(watch_games),
                "raw_output_path": f"raw/{prompt_id}.json",
                "prompt": prompt_with_automation_marker(
                    prompt_id,
                    args.run_id,
                    build_prompt(
                        tool,
                        start_date,
                        end_date,
                        args.lookback_days,
                        args.report_mode,
                        args.max_mihoyo_items,
                        args.max_kuro_items,
                        args.max_market_items,
                        watch_games,
                    ),
                ),
            }
        item.update(fallback_fields(tool, args.run_id, start_date, end_date, args.lookback_days))
        prompts.append(item)
    if not args.skip_community_deep_dive:
        deep_tools = [item.strip() for item in args.community_deep_dive_tools.split(",") if item.strip()]
        unknown_deep_tools = [tool for tool in deep_tools if tool not in AI_TOOLS]
        if unknown_deep_tools:
            raise ValueError(f"Unknown community deep-dive AI tools: {', '.join(unknown_deep_tools)}")
        for tool in deep_tools:
            slug = AI_TOOLS[tool]["slug"]
            prompt_id = f"{slug}_community_deep_dive_001"
            item = {
                    "prompt_id": prompt_id,
                    "stage": "layer2_community_deep_dive",
                    "game_id": "community_deep_dive",
                    "game_name": "社区深挖任务",
                    "ai_tool": tool,
                    "url": AI_TOOLS[tool]["url"],
                    "entry_url": AI_TOOLS[tool]["entry_url"],
                    "entry_mode": AI_TOOLS[tool]["entry_mode"],
                    "platform_focus": AI_TOOLS[tool]["platform_focus"],
                    "time_range": f"{start_date}..{end_date}",
                    "report_mode": args.report_mode,
                    "watch_game_count": len(watch_games),
                    "raw_output_path": f"raw/{prompt_id}.json",
                    "prompt": prompt_with_automation_marker(
                        prompt_id,
                        args.run_id,
                        build_community_deep_dive_prompt(
                            tool,
                            start_date,
                            end_date,
                            args.lookback_days,
                            args.report_mode,
                            args.max_community_items,
                            watch_games,
                        ),
                    ),
            }
            item.update(fallback_fields(tool, args.run_id, start_date, end_date, args.lookback_days))
            prompts.append(item)

    if args.report_mode == "weekly" and not args.skip_weekly_expansion:
        expansion_tools = [item.strip() for item in args.weekly_expansion_tools.split(",") if item.strip()]
        unknown_expansion_tools = [tool for tool in expansion_tools if tool not in AI_TOOLS]
        if unknown_expansion_tools:
            raise ValueError(f"Unknown weekly expansion AI tools: {', '.join(unknown_expansion_tools)}")
        for tool in expansion_tools:
            slug = AI_TOOLS[tool]["slug"]
            prompt_id = f"{slug}_weekly_expansion_001"
            item = {
                "prompt_id": prompt_id,
                "stage": "layer2_weekly_expansion",
                "game_id": "weekly_expansion",
                "game_name": "周报扩展补采",
                "ai_tool": tool,
                "url": AI_TOOLS[tool]["url"],
                "entry_url": AI_TOOLS[tool]["entry_url"],
                "entry_mode": AI_TOOLS[tool]["entry_mode"],
                "platform_focus": AI_TOOLS[tool]["platform_focus"],
                "time_range": f"{start_date}..{end_date}",
                "report_mode": args.report_mode,
                "watch_game_count": len(watch_games),
                "raw_output_path": f"raw/{prompt_id}.json",
                "prompt": prompt_with_automation_marker(
                    prompt_id,
                    args.run_id,
                    build_weekly_expansion_prompt(
                        tool,
                        start_date,
                        end_date,
                        args.lookback_days,
                        args.report_mode,
                        args.max_weekly_expansion_items,
                        watch_games,
                    ),
                ),
            }
            item.update(fallback_fields(tool, args.run_id, start_date, end_date, args.lookback_days))
            prompts.append(item)

    return {
        "report_type": "company_weekly_expanded_scan" if args.report_mode == "weekly" else "company_daily_fast_scan",
        "report_mode": args.report_mode,
        "run_id": args.run_id,
        "created_at": date.today().isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "lookback_days": args.lookback_days,
        "tools": tools,
        "prompt_count": len(prompts),
        "community_deep_dive_enabled": not args.skip_community_deep_dive,
        "community_deep_dive_tools": [] if args.skip_community_deep_dive else [item.strip() for item in args.community_deep_dive_tools.split(",") if item.strip()],
        "weekly_expansion_enabled": args.report_mode == "weekly" and not args.skip_weekly_expansion,
        "weekly_expansion_tools": [] if args.skip_weekly_expansion else [item.strip() for item in args.weekly_expansion_tools.split(",") if item.strip()],
        "game_count": len(PRODUCTS),
        "watch_game_count": len(watch_games),
        "watch_games": watch_games,
        "game_category_lenses": GAME_CATEGORY_LENSES,
        "weekly_sector_lenses": WEEKLY_SECTOR_LENSES,
        "max_mihoyo_items": args.max_mihoyo_items,
        "max_kuro_items": args.max_kuro_items,
        "max_market_items": args.max_market_items,
        "products": PRODUCTS,
        "prompts": prompts,
    }


def write_markdown(pack: dict[str, Any], path: Path) -> None:
    lines = [
        "# Company Daily Web AI Prompt Pack",
        "",
        f"- Run ID: {pack['run_id']}",
        f"- Report mode: {pack.get('report_mode', 'daily')}",
        f"- Collection strategy: {pack.get('collection_strategy', 'legacy_long_scan')}",
        f"- Time window: {pack['start_date']} to {pack['end_date']} ({pack['lookback_days']} days)",
        f"- Tools: {', '.join(pack['tools'])}",
        f"- Prompt count: {pack['prompt_count']}",
        f"- Watch matrix game count: {pack.get('watch_game_count', 0)}",
        "",
    ]
    if pack.get("groups"):
        lines.extend(["## Grouped Short Scan Groups", ""])
        for group in pack["groups"]:
            lines.append(
                f"- {group.get('group_id', '')}: {group.get('group_name', '')} | "
                f"{group.get('game_count', 0)} games | {group.get('target_platform_role', '')}"
            )
        lines.append("")
    if pack.get("game_category_lenses"):
        lines.extend(["## Game Category Lenses", ""])
        for item in pack["game_category_lenses"]:
            lines.append(f"- {item['name']}: {item['focus']} ({item['why']})")
        lines.append("")
    if pack.get("weekly_sector_lenses"):
        lines.extend(["## Weekly Sector Lenses", ""])
        for item in pack["weekly_sector_lenses"]:
            lines.append(f"- {item['sector']}: {item['scope']} Signals: {item['signals']}")
        lines.append("")
    if pack.get("watch_games"):
        lines.extend(["## Watch Game Matrix Summary", ""])
        for game in pack["watch_games"]:
            aliases = " / ".join(str(alias) for alias in game.get("aliases", []) if str(alias).strip())
            lines.append(f"- {game.get('game_id', '')}: {game.get('game_name', '')} | aliases: {aliases}")
        lines.append("")
    for item in pack["prompts"]:
        lines.extend(
            [
                f"## {item['prompt_id']}",
                "",
                f"- AI: {item['ai_tool']}",
                f"- Stage: {item.get('stage', '')}",
                f"- Group: {item.get('group_id', '')} / {item.get('group_name', '')}",
                f"- Game count: {item.get('game_count', '')}",
                f"- Target role: {item.get('target_platform_role', '')}",
                f"- Prompt length chars: {item.get('prompt_length_chars', len(item.get('prompt', '')))}",
                f"- Entry URL: {item['entry_url']}",
                f"- Chat URL: {item['url']}",
                f"- Focus: {item['platform_focus']}",
                f"- Raw output path: `{item['raw_output_path']}`",
                "",
                "```text",
                item["prompt"],
                "```",
                "",
            ]
        )
        if item.get("fallback_prompt"):
            lines.extend(
                [
                    "### Short Fallback Prompt",
                    "",
                    f"- Fallback prompt ID: `{item['fallback_prompt_id']}`",
                    f"- Fallback raw output path: `{item['fallback_raw_output_path']}`",
                    f"- Fallback policy: {item['fallback_policy']}",
                    "",
                    "```text",
                    item["fallback_prompt"],
                    "```",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def safe_run_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or f"company_daily_{date.today():%Y%m%d}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"company_daily_{date.today():%Y%m%d}")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--report-mode", choices=["daily", "weekly"], default="weekly")
    parser.add_argument("--collection-strategy", choices=["grouped_short_scan", "legacy_long_scan"], default="grouped_short_scan")
    parser.add_argument("--groups", default="", help="Comma-separated grouped_short_scan group IDs. Default: all four groups.")
    parser.add_argument("--group-tool-map", default="", help="Optional grouped_short_scan tool map, e.g. group_core_mihoyo_kuro=豆包|Gemini|Grok|知乎直答;group_sector_female_lifestyle=点点|文心一言|千问|Gemini")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--game-list", default="", help="Optional .xlsx/.xls/.csv/.tsv watch matrix. It is used as prompt scope, not as game x AI polling.")
    parser.add_argument("--tools", default=",".join(DEFAULT_TOOLS))
    parser.add_argument("--max-mihoyo-items", type=int, default=12)
    parser.add_argument("--max-kuro-items", type=int, default=8)
    parser.add_argument("--max-market-items", type=int, default=16)
    parser.add_argument("--community-deep-dive-tools", default=",".join(DEFAULT_COMMUNITY_DEEP_DIVE_TOOLS))
    parser.add_argument("--max-community-items", type=int, default=18)
    parser.add_argument("--skip-community-deep-dive", action="store_true")
    parser.add_argument("--weekly-expansion-tools", default=",".join(DEFAULT_WEEKLY_EXPANSION_TOOLS))
    parser.add_argument("--max-weekly-expansion-items", type=int, default=24)
    parser.add_argument("--skip-weekly-expansion", action="store_true")
    args = parser.parse_args()

    args.run_id = safe_run_id(args.run_id)
    if args.lookback_days is None:
        args.lookback_days = 7 if args.report_mode == "weekly" else 3
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pack = build_pack(args)
    prompt_pack = output_dir / "prompt_pack.json"
    prompt_md = output_dir / "prompt_pack.md"
    prompt_pack.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(pack, prompt_md)

    print(
        json.dumps(
            {
                "prompt_pack": str(prompt_pack),
                "prompt_markdown": str(prompt_md),
                "prompt_count": pack["prompt_count"],
                "report_mode": pack.get("report_mode"),
                "collection_strategy": pack.get("collection_strategy", "legacy_long_scan"),
                "group_count": pack.get("group_count", 0),
                "watch_game_count": pack.get("watch_game_count", 0),
                "time_window": f"{pack['start_date']}..{pack['end_date']}",
                "tools": pack["tools"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
