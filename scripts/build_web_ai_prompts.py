#!/usr/bin/env python3
"""Build Web AI matrix prompt packages for public game-community discovery."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


GLOBAL_MATRIX = "global"
DOMESTIC_MATRIX = "domestic"

GLOBAL_AI_SITES = ("Gemini", "Grok", "豆包")
DOMESTIC_AI_SITES = ("豆包", "元宝", "文心一言", "千问", "点点", "知乎直答")
ALL_AI_SITES = tuple(dict.fromkeys([*GLOBAL_AI_SITES, *DOMESTIC_AI_SITES]))

DEFAULT_SITE_URLS = {
    "Gemini": "https://gemini.google.com/app",
    "Grok": "https://grok.com/",
    "豆包": "https://www.doubao.com/chat/?channel=browser_landing_page",
    "元宝": "https://yuanbao.tencent.com/chat/naQivTmsDa",
    "点点": "https://www.xiaohongshu.com/ai_chat",
    "知乎直答": "https://zhida.zhihu.com/",
    "文心一言": "https://wenxin.baidu.com/",
    "千问": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
}

ENTRY_SITE_URLS = {
    "点点": "https://www.xiaohongshu.com/",
}

DOMESTIC_PLATFORM_MARKERS = {
    "douyin", "抖音", "xiaohongshu", "小红书", "rednote", "weibo", "微博",
    "bilibili", "b站", "哔哩", "zhihu", "知乎", "wechat", "weixin", "微信",
    "公众号", "视频号", "快手", "kuaishou", "百度", "baidu", "中文网页", "国内",
}

DOMESTIC_URL_MARKERS = (
    "douyin.com", "xiaohongshu.com", "xhslink.com", "weibo.com", "bilibili.com",
    "b23.tv", "zhihu.com", "weixin.qq.com", "mp.weixin.qq.com", "kuaishou.com", "baidu.com",
)

GLOBAL_PLATFORM_MARKERS = {
    "youtube", "ytb", "twitch", "x", "twitter", "instagram", "tiktok", "reddit", "steam",
}

GLOBAL_MONITOR_PLATFORMS = {
    "Gemini": ["YOUTUBE", "Instagram"],
    "Grok": ["X", "Instagram"],
    "豆包": ["TIKTOK"],
}

DOMESTIC_MONITOR_PLATFORMS = {
    "豆包": ["抖音", "微博", "B站", "中文网页"],
    "元宝": ["微信生态", "公众号", "新闻", "腾讯系内容", "中文网页"],
    "点点": ["小红书", "抖音", "种草内容", "社媒讨论"],
    "知乎直答": ["知乎", "问答讨论", "争议复盘", "中文网页"],
    "文心一言": ["百度", "中文网页", "新闻", "贴吧", "百科/知道生态"],
    "千问": ["中文网页", "新闻", "公开搜索", "社区线索"],
}

PLATFORM_LABELS = {
    "youtube": "YOUTUBE", "ytb": "YOUTUBE", "twitch": "Twitch", "x": "X", "twitter": "X",
    "instagram": "Instagram", "tiktok": "TIKTOK", "reddit": "Reddit", "steam": "Steam",
    "douyin": "抖音", "抖音": "抖音", "xiaohongshu": "小红书", "小红书": "小红书",
    "rednote": "小红书", "weibo": "微博", "微博": "微博", "bilibili": "B站",
    "b站": "B站", "哔哩": "B站", "zhihu": "知乎", "知乎": "知乎",
    "wechat": "微信生态", "weixin": "微信生态", "微信": "微信生态", "公众号": "公众号",
    "kuaishou": "快手", "快手": "快手", "baidu": "百度", "百度": "百度",
}


def needs_xhs_entry(ai_site: str, platforms: Iterable[Any]) -> bool:
    if ai_site != "点点":
        return False
    return any(str(platform or "").strip().casefold() in {"xiaohongshu", "小红书", "rednote"} for platform in platforms)


def normalize_site(site: Any) -> str:
    text = str(site or "").strip()
    folded = text.casefold()
    for candidate in ALL_AI_SITES:
        if folded == candidate.casefold():
            return candidate
    return text


def known_site_names() -> set[str]:
    return set(ALL_AI_SITES)


def is_domestic_platform(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    if not text:
        return False
    if any(marker.casefold() in text for marker in DOMESTIC_PLATFORM_MARKERS):
        return True
    return any(marker in text for marker in DOMESTIC_URL_MARKERS)


def matrix_for_platforms(platforms: Iterable[Any], links: Iterable[Any] | None = None) -> str:
    for platform in platforms:
        if is_domestic_platform(platform):
            return DOMESTIC_MATRIX
    for link in links or []:
        if is_domestic_platform(link):
            return DOMESTIC_MATRIX
    return GLOBAL_MATRIX


def matrix_for_counts(platform_counts: dict[str, int] | Counter[str], links: Iterable[Any] | None = None) -> str:
    return matrix_for_platforms(platform_counts.keys(), links)


def matrix_label(matrix: str) -> str:
    return "国内AI矩阵" if matrix == DOMESTIC_MATRIX else "海外AI矩阵"


def site_list(matrix: str, requested_ai_tools: Iterable[Any] | None = None) -> tuple[str, ...]:
    requested = [normalize_site(site) for site in (requested_ai_tools or [])]
    known_requested = [site for site in requested if site in known_site_names()]
    if known_requested:
        return tuple(dict.fromkeys(known_requested))
    return DOMESTIC_AI_SITES if matrix == DOMESTIC_MATRIX else GLOBAL_AI_SITES


def monitor_platforms(ai_site: str, matrix: str, row_platforms: Iterable[Any]) -> str:
    defaults = (
        DOMESTIC_MONITOR_PLATFORMS.get(ai_site)
        if matrix == DOMESTIC_MATRIX
        else GLOBAL_MONITOR_PLATFORMS.get(ai_site)
    ) or ["全网公开平台"]
    ordered = list(defaults)
    for platform in row_platforms:
        text = str(platform or "").strip().casefold()
        label = PLATFORM_LABELS.get(text)
        if label and label not in ordered:
            ordered.append(label)
    return "、".join(ordered)


def load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def task_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("task", payload)


def query_samples(payload: dict[str, Any], limit: int = 12) -> list[str]:
    queries: list[str] = []
    for key in ("precise_queries", "broad_queries", "sentiment_queries", "issue_queries", "category_queries", "comparison_queries", "trend_queries"):
        queries.extend(str(value) for value in (payload.get(key) or []))
    return queries[:limit]


def target_label(task: dict[str, Any]) -> str:
    targets = task.get("game_names") or task.get("category_terms") or task.get("keywords") or ["游戏社区舆情"]
    return "、".join(str(item) for item in targets)


def build_prompt(ai_site: str, matrix: str, task: dict[str, Any], queries: list[str]) -> str:
    platforms = task.get("platforms") or ["全网公开平台"]
    goals = task.get("analysis_goals") or ["player_opinion", "sentiment"]
    time_range = task.get("time_range") or "未指定时间范围，以近期公开可检索内容为主"
    query_block = "\n".join(f"- {query}" for query in queries) or "- 请基于目标自行扩展公开检索词"
    xhs_rules = ""
    if needs_xhs_entry(ai_site, platforms):
        xhs_rules = """
点点/小红书专项要求：
1. 本轮必须优先从小红书普通页面或小红书场景入口进入点点，而不是只在点点通用首页直接泛问。
2. 必须优先返回 xiaohongshu.com 或 xhslink.com 的可核查笔记/搜索结果链接。
3. 只有标题、只有 AI 概括、没有 URL 的小红书内容，必须放入 pending_leads / 待验证线索，不得进入候选证据。
4. 如果小红书入口不可用、需要登录、验证码或权限限制，请明确标注 access_status 与 limitations。
"""
    return f"""请只基于公开可访问或搜索可验证的网页，辅助检索并总结游戏社区舆情。

目标：{target_label(task)}
平台：{"、".join(str(p) for p in platforms)}
时间范围：{time_range}
分析目标：{"、".join(str(g) for g in goals)}
AI工具：{ai_site}
AI矩阵：{matrix_label(matrix)}
你负责重点观察：{monitor_platforms(ai_site, matrix, platforms)}
工具身份防漂移：AI工具名只表示提交问题的平台，不是检索对象；不要把千问/Qwen/通义千问/阿里AI助手/豆包/元宝/文心一言/Gemini/Grok等 AI 工具官网、产品介绍页、API服务页或下载页当成游戏舆情来源。
{xhs_rules}

参考检索词：
{query_block}

请按 JSON 数组返回候选证据，每条包含：
- platform
- title
- url
- published_at
- snippet
- summary
- access_status: accessible / search_snippet_only / blocked_login / forbidden_403 / captcha / paywalled / no_url / unknown
- limitations

硬性要求：
1. 没有 URL 的内容只能放入待验证线索，不得放入核心证据。
2. 不要编造帖子链接、标题、时间或玩家原话。
3. 不要尝试绕过登录、403、验证码、付费墙或私密群。
4. 如果只能看到搜索片段，请标记 access_status=search_snippet_only。
5. 最后单独列出 3-5 条可用于扩展检索的关键词。"""


def build_prompt_pack(payload: dict[str, Any]) -> dict[str, Any]:
    task = task_from_payload(payload)
    platforms = task.get("platforms") or []
    links = payload.get("links") or []
    matrix = matrix_for_platforms(platforms, links)
    sites = site_list(matrix, task.get("requested_ai_tools"))
    queries = query_samples(payload)
    return {
        "matrix": matrix,
        "matrix_label": matrix_label(matrix),
        "routing_policy": "Explicit AI tools are honored when provided; otherwise route by all known platform and URL markers.",
        "known_ai_tools": list(ALL_AI_SITES),
        "task": task,
        "prompts": [
            {
                "ai_site": site,
                "url": DEFAULT_SITE_URLS.get(site, ""),
                "entry_url": ENTRY_SITE_URLS.get(site, "") if needs_xhs_entry(site, platforms) else "",
                "entry_mode": "open_entry_then_launch_ai" if needs_xhs_entry(site, platforms) else "direct",
                "monitor_platforms": monitor_platforms(site, matrix, platforms),
                "prompt": build_prompt(site, matrix, task, queries),
            }
            for site in sites
        ],
    }


def write_markdown(pack: dict[str, Any], path: str) -> None:
    lines = ["# Web AI Matrix Prompts", "", f"- Matrix: {pack['matrix_label']}", f"- Policy: {pack['routing_policy']}", ""]
    for item in pack["prompts"]:
        lines.extend([f"## {item['ai_site']}", "", f"- URL: {item['url']}", f"- Monitor: {item['monitor_platforms']}", "", "```text", item["prompt"], "```", ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query_pack_or_task", help="Path to query_pack.json or parsed task JSON")
    parser.add_argument("--output", "-o", default="web_ai_prompts.json")
    parser.add_argument("--markdown-output", default="web_ai_prompts.md")
    args = parser.parse_args()

    pack = build_prompt_pack(load_json(args.query_pack_or_task))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_markdown(pack, args.markdown_output)
    print(json.dumps({"output": args.output, "markdown_output": args.markdown_output, "matrix": pack["matrix"], "sites": [p["ai_site"] for p in pack["prompts"]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
