#!/usr/bin/env python3
"""Parse a natural-language game community intelligence request into JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


SUPPORTED_PLATFORMS = [
    "NGA",
    "TapTap",
    "Steam",
    "Bilibili",
    "Weibo",
    "Xiaohongshu",
    "Tieba",
    "Reddit",
    "Douyin",
    "Zhihu",
    "WeChat",
    "Kuaishou",
    "Baidu",
    "YouTube",
    "X",
    "Instagram",
    "TikTok",
    "Twitch",
]

PLATFORM_ALIASES = {
    "NGA": ["nga", "ngabbs", "艾泽拉斯国家地理"],
    "TapTap": ["taptap", "tap tap"],
    "Steam": ["steam", "steampowered"],
    "Bilibili": ["b站", "bilibili", "哔哩哔哩", "哔哩"],
    "Weibo": ["微博", "weibo"],
    "Xiaohongshu": ["小红书", "xiaohongshu", "rednote"],
    "Tieba": ["贴吧", "tieba", "百度贴吧"],
    "Reddit": ["reddit", "subreddit"],
    "Douyin": ["抖音", "douyin"],
    "Zhihu": ["知乎", "zhihu"],
    "WeChat": ["微信", "weixin", "wechat", "公众号", "视频号"],
    "Kuaishou": ["快手", "kuaishou"],
    "Baidu": ["百度", "baidu", "中文网页"],
    "YouTube": ["youtube", "ytb"],
    "X": ["twitter", "x平台", "x/twitter"],
    "Instagram": ["instagram", "ins"],
    "TikTok": ["tiktok"],
    "Twitch": ["twitch"],
}

AI_TOOL_ALIASES = {
    "Gemini": ["gemini"],
    "Grok": ["grok"],
    "豆包": ["豆包", "doubao"],
    "元宝": ["元宝", "yuanbao"],
    "点点": ["点点", "diandian", "dots.ai", "dots"],
    "知乎直答": ["知乎直答", "zhida", "zhida.zhihu"],
    "文心一言": ["文心一言", "文心", "一言", "yiyan", "ernie", "百度ai", "百度 AI"],
    "千问": ["千问", "通义千问", "qianwen", "qwen", "tongyi", "阿里ai", "阿里 AI"],
}

ALL_PLATFORM_TOKENS = ["全平台", "所有平台", "全网", "多平台", "各个平台", "各平台", "全渠道"]

KNOWN_GAMES = [
    "原神",
    "绝区零",
    "崩坏：星穹铁道",
    "崩坏星穹铁道",
    "星穹铁道",
    "鸣潮",
    "明日方舟",
    "王者荣耀",
    "和平精英",
    "逆水寒",
    "永劫无间",
    "恋与深空",
    "光与夜之恋",
    "未定事件簿",
    "如鸢",
    "世界之外",
    "以闪亮之名",
]

CATEGORY_TERMS = [
    "二游",
    "二次元",
    "二次元手游",
    "开放世界",
    "开放世界手游",
    "女性向",
    "乙女",
    "卡牌",
    "抽卡",
    "放置",
    "SLG",
    "MMO",
    "MMORPG",
    "FPS",
    "射击",
    "生存",
    "肉鸽",
    "Roguelike",
    "派对游戏",
    "休闲游戏",
    "独立游戏",
    "国产手游",
    "买断制",
    "服务型游戏",
    "动作手游",
    "策略游戏",
]

GOAL_KEYWORDS = {
    "player_opinion": ["玩家意见", "意见", "反馈", "讨论", "评价", "口碑"],
    "sentiment": ["舆情", "情绪", "好评", "差评", "正面", "负面"],
    "controversy": ["争议", "节奏", "吵", "炎上", "骂"],
    "risk": ["风险", "预警", "危机"],
    "version_feedback": ["版本", "更新", "新版本", "活动"],
    "comparison": ["对比", "比较", "差异", "竞品"],
    "design_lessons": ["借鉴", "设计点", "可学", "启发"],
    "trend": ["发展", "趋势", "演变", "扩散", "发酵"],
}

TOPIC_KEYWORDS = ["剧情", "角色", "玩法", "氪金", "优化", "活动", "版本", "BUG", "bug", "回坑", "入坑", "退坑", "竞品"]


def find_platforms(text: str) -> list[str]:
    lowered = text.lower()
    if any(token in text for token in ALL_PLATFORM_TOKENS):
        return SUPPORTED_PLATFORMS.copy()
    platforms = []
    for platform, aliases in PLATFORM_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            platforms.append(platform)
    return platforms


def find_ai_tools(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for tool, aliases in AI_TOOL_ALIASES.items():
        positions = [lowered.find(alias.lower()) for alias in aliases if alias.lower() in lowered]
        if positions:
            matches.append((min(positions), tool))
    return [tool for _, tool in sorted(matches, key=lambda item: item[0])]


def find_time_range(text: str) -> str:
    patterns = [
        r"最近\s*\d+\s*天",
        r"近\s*\d+\s*天",
        r"最近\s*\d+\s*周",
        r"近\s*\d+\s*周",
        r"最近\s*\d+\s*个月",
        r"近\s*\d+\s*个月",
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*(?:到|至|-|~)\s*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?",
        r"last\s+\d+\s+days?",
        r"past\s+\d+\s+days?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    if any(token in text for token in ["最近", "近期", " lately", "recent"]):
        return "最近 7 天"
    return ""


def find_goals(text: str) -> list[str]:
    lowered = text.lower()
    goals = [goal for goal, keywords in GOAL_KEYWORDS.items() if any(keyword.lower() in lowered for keyword in keywords)]
    return goals or ["player_opinion", "sentiment"]


def find_keywords(text: str) -> list[str]:
    return [keyword for keyword in TOPIC_KEYWORDS if keyword in text]


def find_categories(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in CATEGORY_TERMS if term.lower() in lowered]


def find_games(text: str, platforms: list[str], time_range: str, goals: list[str], categories: list[str], ai_tools: list[str]) -> list[str]:
    games = [game for game in KNOWN_GAMES if game in text]
    if games:
        return games
    if categories:
        return []

    cleaned = text
    for platform in platforms:
        for alias in PLATFORM_ALIASES.get(platform, []):
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    for tool in ai_tools:
        for alias in AI_TOOL_ALIASES.get(tool, []):
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    for token in [time_range, *ALL_PLATFORM_TOKENS, *categories]:
        if token:
            cleaned = cleaned.replace(token, " ")
    stop_tokens = ["分析", "社区", "最近", "近期", "玩家", "意见", "舆情", "讨论", "反馈", "关于", "平台", "内容", "类型", "品类", "工具", "AI", "ai"]
    for token in [*stop_tokens, *TOPIC_KEYWORDS]:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"[，。、“”\"'：:；;,.!?？\[\]（）()]", " ", cleaned)
    candidates = [part.strip() for part in re.split(r"\s+", cleaned) if len(part.strip()) >= 2]
    stop = set(goals + ["game", "community", "sentiment", "version", "feedback"])
    return [candidate for candidate in candidates if candidate.lower() not in stop][:3]


def parse_task(text: str) -> dict[str, Any]:
    platforms = find_platforms(text)
    ai_tools = find_ai_tools(text)
    time_range = find_time_range(text)
    goals = find_goals(text)
    keywords = find_keywords(text)
    categories = find_categories(text)
    games = find_games(text, platforms, time_range, goals, categories, ai_tools)
    analysis_scope = "category_scan" if categories and not games else "game_specific"
    if len(platforms) >= 2:
        analysis_scope = "all_platform_trend" if any(token in text for token in ALL_PLATFORM_TOKENS) else "cross_platform"
    return {
        "platforms": platforms,
        "game_names": games,
        "category_terms": categories,
        "time_range": time_range,
        "analysis_goals": goals,
        "keywords": keywords,
        "requested_ai_tools": ai_tools,
        "analysis_scope": analysis_scope,
        "source_policy": "public_indexed_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="*", help="Natural-language user question")
    parser.add_argument("--output", "-o", help="Write JSON to this path")
    args = parser.parse_args()

    text = " ".join(args.question).strip() or sys.stdin.read().strip()
    if not text:
        raise SystemExit("Provide a question via argv or stdin.")

    result = parse_task(text)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
