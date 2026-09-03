#!/usr/bin/env python3
"""Build public-web search queries from parsed task JSON."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


PLATFORM_PATTERNS = {
    "NGA": {
        "precise": ["site:ngabbs.com/read.php {target} 玩家意见", "site:ngabbs.com/read.php {target} 剧情 吐槽", "site:ngabbs.com/read.php {target} 版本 争议"],
        "broad": ["NGA {target} 玩家 舆情", "NGA {target} 争议 版本"],
    },
    "TapTap": {
        "precise": ["site:taptap.cn {target} 评价", "site:taptap.cn {target} 新版本 反馈", "site:taptap.cn {target} 差评"],
        "broad": ["TapTap {target} 玩家 口碑", "TapTap {target} 优化 BUG 氪金"],
    },
    "Steam": {
        "precise": ["site:steamcommunity.com/app {target} review negative", "site:store.steampowered.com/app {target} reviews"],
        "broad": ["Steam {target} 差评 原因", "Steam {target} recent reviews negative"],
    },
    "Bilibili": {
        "precise": ["site:bilibili.com/video {target} 新版本 评价", "site:bilibili.com/read {target} 玩家 反馈"],
        "broad": ["B站 {target} 吐槽", "Bilibili {target} 争议 版本", "{target} 评论区 玩家 反馈 B站"],
    },
    "Weibo": {
        "precise": ["site:weibo.com {target} 玩家 反馈", "site:weibo.com {target} 超话"],
        "broad": ["微博 {target} 新版本 争议", "微博 {target} 超话 吐槽", "{target} 微博 氪金 优化 BUG"],
    },
    "Xiaohongshu": {
        "precise": ["site:xiaohongshu.com {target} 游戏 体验", "site:xiaohongshu.com {target} 新版本"],
        "broad": ["小红书 {target} 新手 入坑", "小红书 {target} 吐槽", "{target} 小红书 避雷 推荐"],
    },
    "Tieba": {
        "precise": ["site:tieba.baidu.com/p {target} 玩家 反馈"],
        "broad": ["{target} 吧 新版本 吐槽", "{target} 贴吧 争议"],
    },
    "Reddit": {
        "precise": ["site:reddit.com/r/ {target} discussion", "site:reddit.com/r/ {target} update feedback"],
        "broad": ["Reddit {target} controversy", "Reddit {target} review negative", "{target} subreddit player feedback"],
    },
    "Douyin": {
        "precise": ["site:douyin.com {target} 游戏", "site:douyin.com {target} 玩家"],
        "broad": ["抖音 {target} 吐槽", "抖音 {target} 玩家反馈", "{target} 抖音 热评"],
    },
    "Zhihu": {
        "precise": ["site:zhihu.com/question {target} 游戏", "site:zhihu.com {target} 玩家评价"],
        "broad": ["知乎 {target} 如何评价", "知乎 {target} 争议 复盘"],
    },
    "WeChat": {
        "precise": ["site:mp.weixin.qq.com {target} 游戏", "site:weixin.qq.com {target} 玩家"],
        "broad": ["微信公众号 {target} 舆情", "微信 {target} 玩家 反馈"],
    },
    "Kuaishou": {
        "precise": ["site:kuaishou.com {target} 游戏"],
        "broad": ["快手 {target} 玩家反馈", "快手 {target} 吐槽"],
    },
    "Baidu": {
        "precise": ["site:baidu.com {target} 游戏 舆情"],
        "broad": ["百度 {target} 玩家反馈", "中文网页 {target} 争议"],
    },
    "YouTube": {
        "precise": ["site:youtube.com/watch {target} review", "site:youtube.com/watch {target} update"],
        "broad": ["YouTube {target} player feedback", "YouTube {target} controversy"],
    },
    "X": {
        "precise": ["site:x.com {target} game", "site:twitter.com {target} game"],
        "broad": ["X Twitter {target} controversy", "X Twitter {target} player feedback"],
    },
    "Instagram": {
        "precise": ["site:instagram.com {target} game"],
        "broad": ["Instagram {target} player reaction", "Instagram {target} fan discussion"],
    },
    "TikTok": {
        "precise": ["site:tiktok.com {target} game"],
        "broad": ["TikTok {target} player reaction", "TikTok {target} controversy"],
    },
    "Twitch": {
        "precise": ["site:twitch.tv {target} game"],
        "broad": ["Twitch {target} streamer reaction", "Twitch {target} player discussion"],
    },
}

SENTIMENT_TERMS = ["好评", "差评", "吐槽", "争议", "口碑", "退坑", "回坑"]
ISSUE_TERMS = ["剧情", "角色", "玩法", "氪金", "优化", "活动", "版本", "BUG"]
CATEGORY_DISCOVERY_TERMS = ["代表游戏", "玩家讨论", "口碑", "近期争议", "新版本反馈", "避雷", "推荐"]


def load_task(path: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if not path or path == "-" else open(path, encoding="utf-8").read()
    return json.loads(raw)


def unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def targets_for(task: dict[str, Any]) -> list[str]:
    games = task.get("game_names") or []
    categories = task.get("category_terms") or []
    if games:
        return games
    if categories:
        return categories
    return ["游戏"]


def build_query_pack(task: dict[str, Any]) -> dict[str, Any]:
    targets = targets_for(task)
    platforms = task.get("platforms") or ["Web"]
    time_range = task.get("time_range") or ""
    keywords = task.get("keywords") or []
    categories = task.get("category_terms") or []
    scope = task.get("analysis_scope") or "game_specific"

    precise: list[str] = []
    broad: list[str] = []
    sentiment: list[str] = []
    issues: list[str] = []
    category_queries: list[str] = []
    comparisons: list[str] = []
    trends: list[str] = []

    for target in targets:
        for platform in platforms:
            patterns = PLATFORM_PATTERNS.get(platform)
            if patterns:
                precise.extend(pattern.format(target=target) for pattern in patterns["precise"])
                broad.extend(pattern.format(target=target) for pattern in patterns["broad"])
            else:
                broad.extend([f"{platform} {target} 玩家 反馈", f"{platform} {target} 舆情 争议"])

        active_terms = keywords or ISSUE_TERMS
        for term in SENTIMENT_TERMS:
            sentiment.append(f"{target} {term} 玩家反馈 {time_range}".strip())
        for term in active_terms:
            issues.append(f"{target} {term} 玩家意见 {time_range}".strip())

        if categories or scope == "category_scan":
            for term in CATEGORY_DISCOVERY_TERMS:
                category_queries.append(f"{target} {term} {time_range}".strip())
            category_queries.extend([f"TapTap {target} 评价 排名", f"小红书 {target} 入坑 避雷", f"B站 {target} 节奏 版本", f"NGA {target} 玩家 争议"])

        if scope in {"all_platform_trend", "cross_platform"} or len(platforms) >= 2:
            comparisons.append(f"{' vs '.join(platforms)} {target} 舆情 差异")
            comparisons.append(f"{' 与 '.join(platforms)} 对 {target} 评价 差异")
            trends.append(f"{target} 舆情 发酵 时间线 {time_range}".strip())
            trends.append(f"{target} 全平台 玩家情绪 变化 {time_range}".strip())

    if len(targets) >= 2:
        comparisons.append(f"{' vs '.join(targets)} 玩家口碑 争议 对比")

    return {
        "task": task,
        "precise_queries": unique(precise),
        "broad_queries": unique(broad),
        "sentiment_queries": unique(sentiment),
        "issue_queries": unique(issues),
        "category_queries": unique(category_queries),
        "comparison_queries": unique(comparisons),
        "trend_queries": unique(trends),
        "notes": [
            "Use public indexed results only.",
            "Do not bypass login, 403, CAPTCHA, paywalls, or private communities.",
            "Web AI outputs without URLs are secondary_only leads.",
            "For category-only tasks, identify surfaced games/topics but do not imply full-market coverage.",
            "For all-platform tasks, report platform differences and propagation timeline separately.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_json", nargs="?", default="-", help="Parsed task JSON path, or stdin")
    parser.add_argument("--output", "-o", help="Write query pack JSON to this path")
    args = parser.parse_args()

    pack = build_query_pack(load_task(args.task_json))
    payload = json.dumps(pack, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
