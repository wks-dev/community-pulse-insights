#!/usr/bin/env python3
"""Build daily Web AI prompts for a normalized game list."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


AI_TOOLS = {
    "Gemini": {
        "url": "https://gemini.google.com/app",
        "platforms": ["YouTube", "Instagram", "global web"],
    },
    "Grok": {
        "url": "https://grok.com/",
        "platforms": ["X", "Instagram", "global social"],
    },
    "豆包": {
        "url": "https://www.doubao.com/chat/?channel=browser_landing_page",
        "platforms": ["抖音", "微博", "B站", "中文网页", "TikTok"],
    },
    "元宝": {
        "url": "https://yuanbao.tencent.com/chat/naQivTmsDa",
        "platforms": ["微信生态", "公众号", "新闻", "腾讯系内容", "中文网页"],
    },
    "点点": {
        "url": "https://www.xiaohongshu.com/ai_chat",
        "entry_url": "https://www.xiaohongshu.com/",
        "entry_mode": "open_entry_then_launch_ai",
        "platforms": ["小红书", "抖音", "种草内容", "社媒讨论"],
    },
    "知乎直答": {
        "url": "https://zhida.zhihu.com/",
        "platforms": ["知乎", "问答讨论", "争议复盘", "中文网页"],
    },
    "文心一言": {
        "url": "https://wenxin.baidu.com/",
        "platforms": ["百度", "中文网页", "新闻", "贴吧", "百科/知道生态"],
    },
    "千问": {
        "url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_mode": "direct",
        "platforms": ["中文网页", "新闻", "公开搜索", "社区线索"],
    },
}

DEFAULT_TOOLS = ["豆包", "元宝", "文心一言", "千问", "点点", "知乎直答", "Gemini", "Grok"]


def load_games(path: str) -> list[dict[str, Any]]:
    data = json.load(open(path, encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    return data.get("games", [])


def chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def game_lines(games: list[dict[str, Any]]) -> str:
    lines = []
    for game in games:
        aliases = " / ".join(game.get("aliases") or [game.get("game_name", "")])
        notes = game.get("notes") or ""
        lines.append(f"- {game.get('game_id')}: {game.get('game_name')} | aliases: {aliases} | notes: {notes}")
    return "\n".join(lines)


def build_prompt(ai_tool: str, games: list[dict[str, Any]], lookback_hours: int, report_date: str) -> str:
    info = AI_TOOLS[ai_tool]
    platforms = "、".join(info["platforms"])
    identity_guard = f"""
工具身份防漂移：
1. 当前 AI 工具“{ai_tool}”只表示本轮提交问题的平台，不是检索对象。
2. 不要把千问、Qwen、通义千问、阿里 AI 助手、豆包、元宝、文心一言、Gemini、Grok 等 AI 工具官网、产品介绍页、API 服务页或下载页当成游戏舆情来源。
3. 本轮唯一检索对象是下面游戏名单中的游戏名、别名、厂商和玩家社区主题。
"""
    entry_rules = ""
    if ai_tool == "点点":
        entry_rules = """

点点/小红书专项要求：
1. 本轮必须优先从小红书普通页面或小红书场景入口进入点点，而不是只在点点通用首页直接泛问。
2. 必须优先返回 xiaohongshu.com 或 xhslink.com 的可核查笔记/搜索结果链接。
3. 只有标题、只有 AI 概括、没有 URL 的小红书内容，必须放入 pending_leads，不得放入 evidence。
4. 如果小红书入口不可用、需要登录、验证码或权限限制，请明确标注 access_status 与 limitations。
"""
    if ai_tool == "千问":
        entry_rules = """

千问专项要求：
1. 入口应为 https://www.qianwen.com/ 的普通文字对话页。
2. 千问只是本轮使用的 AI 工具，不是检索目标；不要检索或总结“千问”“Qwen”“通义千问”“阿里 AI 助手”官网、本页面、API 服务或下载页。
3. 优先覆盖中文网页、新闻、公开搜索与跨平台社区线索。
4. 如果结果只返回千问/通义/Qwen/阿里 AI 助手产品介绍，视为检索漂移：不要写入 evidence 或 pending_leads，必须换用游戏名/别名重新检索。
5. 不要误入 API 服务、下载电脑端、PPT创作、AI生图、AI生视频、翻译、代码等专项工具。
6. 没有可核查 URL 的内容必须放入 pending_leads。
"""
    return f"""你是游戏行业舆情检索助手。请只基于公开可访问或搜索可验证的网页，为以下游戏名单检索最近 {lookback_hours} 小时内值得关注的玩家讨论、帖子、视频、问答、新闻或社区事件。

当前 AI 工具：{ai_tool}
重点覆盖平台/内容面：{platforms}
报告日期：{report_date}
{identity_guard}
{entry_rules}

游戏名单：
{game_lines(games)}

请优先寻找：
1. 新版本反馈、活动反馈、福利、抽卡争议
2. BUG、优化、卡顿、掉帧、闪退
3. 剧情、角色、CP、女性向/二游敏感点
4. 退坑、回流、停氪、差评、炎上
5. 值得关注的帖子、评论区、视频、问答或新闻
6. 玩家倾向：正面、负面、中立、分化、观望
7. 事件趋势：新增、升温、降温、延续

请返回严格 JSON，不要返回解释文字。格式：
{{
  "ai_tool": "{ai_tool}",
  "covered_platforms": {json.dumps(info["platforms"], ensure_ascii=False)},
  "evidence": [
    {{
      "game_id": "game_001",
      "game_name": "游戏名",
      "matched_alias": "命中的别名",
      "platform": "平台",
      "source_ai": "{ai_tool}",
      "title": "帖子/视频/问答/新闻标题",
      "url": "https://...",
      "published_at": "YYYY-MM-DD 或相对时间",
      "event_type": "版本更新 | 争议 | BUG | 优化 | 福利 | 活动 | 角色 | 剧情 | 竞品比较 | 其他",
      "player_tendency": "正面 | 负面 | 中立 | 分化 | 观望",
      "sentiment": "positive | negative | neutral | mixed",
      "risk_level": "low | medium | high",
      "snippet": "可见片段或可访问摘录",
      "summary": "基于证据的一句话摘要",
      "why_watch": "为什么今天值得关注",
      "access_status": "accessible | search_snippet_only | blocked_login | forbidden_403 | captcha | paywalled | no_url | unknown",
      "limitations": "样本限制"
    }}
  ],
  "pending_leads": [
    {{
      "game_id": "game_001",
      "lead": "没有 URL 或暂未验证的线索",
      "reason": "为什么需要后续验证"
    }}
  ],
  "expanded_keywords": ["关键词1", "关键词2", "关键词3"]
}}

硬性要求：
1. 没有 URL 或无法验证的内容必须放入 pending_leads，不得放入 evidence。
2. 不要编造链接、标题、时间、玩家原话或数据。
3. 不要绕过登录、验证码、403、付费墙或私密群。
4. 如果只能看到搜索片段，请标记 access_status=search_snippet_only。
5. evidence 中每条都必须能支持日报中的一个具体结论。"""


def build_pack(games: list[dict[str, Any]], tools: list[str], chunk_size: int, lookback_hours: int, report_date: str) -> dict[str, Any]:
    prompts = []
    for tool in tools:
        if tool not in AI_TOOLS:
            continue
        for idx, group in enumerate(chunks(games, chunk_size), start=1):
            prompts.append(
                {
                    "prompt_id": f"{tool}_batch_{idx:02d}",
                    "ai_tool": tool,
                    "url": AI_TOOLS[tool]["url"],
                    "entry_url": AI_TOOLS[tool].get("entry_url", ""),
                    "entry_mode": AI_TOOLS[tool].get("entry_mode", "direct"),
                    "covered_platforms": AI_TOOLS[tool]["platforms"],
                    "game_count": len(group),
                    "game_ids": [game["game_id"] for game in group],
                    "prompt": build_prompt(tool, group, lookback_hours, report_date),
                }
            )
    return {
        "report_date": report_date,
        "lookback_hours": lookback_hours,
        "game_count": len(games),
        "tools": tools,
        "prompts": prompts,
    }


def write_markdown(pack: dict[str, Any], path: str) -> None:
    lines = [
        "# Daily Web AI Prompts",
        "",
        f"- Report date: {pack['report_date']}",
        f"- Lookback hours: {pack['lookback_hours']}",
        f"- Games: {pack['game_count']}",
        f"- Tools: {', '.join(pack['tools'])}",
        "",
    ]
    for item in pack["prompts"]:
        lines.extend(
            [
                f"## {item['prompt_id']}",
                "",
                f"- AI: {item['ai_tool']}",
                f"- URL: {item['url']}",
                f"- Platforms: {'、'.join(item['covered_platforms'])}",
                f"- Games: {', '.join(item['game_ids'])}",
                "",
                "```text",
                item["prompt"],
                "```",
                "",
            ]
        )
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list_json", help="Path to normalized game_list.json")
    parser.add_argument("--tools", default=",".join(DEFAULT_TOOLS), help="Comma-separated AI tools")
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--output", "-o", default="daily_ai_prompts.json")
    parser.add_argument("--markdown-output", default="daily_ai_prompts.md")
    args = parser.parse_args()

    tools = [tool.strip() for tool in args.tools.split(",") if tool.strip()]
    pack = build_pack(load_games(args.game_list_json), tools, args.chunk_size, args.lookback_hours, args.report_date)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_markdown(pack, args.markdown_output)
    print(json.dumps({"output": args.output, "markdown_output": args.markdown_output, "prompts": len(pack["prompts"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
