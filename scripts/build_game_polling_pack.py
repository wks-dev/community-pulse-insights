#!/usr/bin/env python3
"""Build one-game-per-AI Web AI polling prompts from a game list."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from load_game_list import read_spreadsheet  # noqa: E402


AI_TOOLS: dict[str, dict[str, Any]] = {
    "元宝": {
        "url": "https://yuanbao.tencent.com/chat/naQivTmsDa",
        "platform_focus": "微信生态、公众号、新闻、腾讯系内容、中文网页",
    },
    "豆包": {
        "url": "https://www.doubao.com/chat/?channel=browser_landing_page",
        "platform_focus": "抖音、微博、B站、中文网页、新闻、TikTok线索",
    },
    "文心一言": {
        "url": "https://wenxin.baidu.com/",
        "platform_focus": "百度、中文网页、新闻、贴吧、百度知道/百科生态",
    },
    "千问": {
        "url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "entry_mode": "direct",
        "platform_focus": "中文网页、新闻、公开搜索、跨平台社区线索；千问只是执行工具，不是检索对象",
    },
    "点点": {
        "url": "https://www.xiaohongshu.com/ai_chat",
        "entry_url": "https://www.xiaohongshu.com/",
        "entry_mode": "open_xiaohongshu_then_ai_chat",
        "platform_focus": "小红书、种草内容、社媒讨论；优先返回 xiaohongshu.com 或 xhslink.com 证据",
    },
    "知乎直答": {
        "url": "https://zhida.zhihu.com/",
        "platform_focus": "知乎问答、争议复盘、中文网页",
    },
    "Gemini": {
        "url": "https://gemini.google.com/app",
        "platform_focus": "全球公开网页、YouTube、Instagram",
    },
    "Grok": {
        "url": "https://grok.com/",
        "platform_focus": "X/Twitter、全球社媒、实时公开讨论",
    },
}

DEFAULT_TOOLS = ["元宝", "豆包", "文心一言", "千问", "点点", "知乎直答", "Gemini", "Grok"]


def slugify(value: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(value or "game")).strip("_")
    return text[:80] or "game"


def load_template(path: Path | None) -> str:
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    ref = SKILL_DIR / "references" / "universal_game_polling_prompt.md"
    text = ref.read_text(encoding="utf-8")
    match = re.search(r"```text\s*(.*?)```", text, flags=re.S)
    if not match:
        raise ValueError(f"Cannot find text prompt block in {ref}")
    return match.group(1).strip()


def tool_identity_guard(tool: str) -> str:
    return (
        f"工具身份防漂移：当前 AI 工具“{tool}”只表示本轮提交问题的平台，不是检索对象；"
        "不要把千问/Qwen/通义千问/阿里AI助手/豆包/元宝/文心一言/Gemini/Grok等 AI 工具官网、"
        "产品介绍页、API服务页或下载页当成游戏舆情来源；唯一检索对象是游戏名、别名、厂商和玩家社区主题。"
    )


def render_prompt(template: str, game: dict[str, Any], tool: str, start_date: str, end_date: str, max_items: int) -> str:
    aliases = game.get("aliases") or [game.get("game_name", "")]
    values = {
        "game_id": game.get("game_id", ""),
        "game_name": game.get("game_name", ""),
        "aliases": " / ".join(aliases),
        "aliases_json": json.dumps(aliases, ensure_ascii=False),
        "ai_tool": tool,
        "platform_focus": AI_TOOLS[tool]["platform_focus"],
        "tool_identity_guard": tool_identity_guard(tool),
        "start_date": start_date,
        "end_date": end_date,
        "max_items": str(max_items),
    }
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace("{" + key + "}", str(value))
    return prompt


def prompt_with_automation_marker(prompt_id: str, run_id: str, prompt: str) -> str:
    marker = (
        "AUTOMATION_MARKER (for browser automation only; do not use as a search keyword): "
        f"COLLECT_RUN_ID={run_id}; PROMPT_ID={prompt_id}"
    )
    return f"{marker}\n\n{prompt.strip()}"


def write_grouped_markdown(pack: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    by_ai = output_dir / "prompts_by_ai"
    by_game = output_dir / "prompts_by_game"
    by_ai.mkdir(parents=True, exist_ok=True)
    by_game.mkdir(parents=True, exist_ok=True)

    prompts = pack["prompts"]
    for tool in pack["tools"]:
        lines = [f"# {tool} prompt queue", ""]
        for item in prompts:
            if item["ai_tool"] != tool:
                continue
            lines.extend([f"## {item['prompt_id']}", "", item["prompt"], ""])
        (by_ai / f"{slugify(tool)}.md").write_text("\n".join(lines), encoding="utf-8")

    for game in pack["games"]:
        lines = [f"# {game['game_id']} {game['game_name']}", ""]
        for item in prompts:
            if item["game_id"] != game["game_id"]:
                continue
            lines.extend([f"## {item['ai_tool']}", "", item["prompt"], ""])
        (by_game / f"{game['game_id']}_{slugify(game['game_name'])}.md").write_text("\n".join(lines), encoding="utf-8")
    return by_ai, by_game


def write_manifest(pack: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["prompt_id", "game_id", "game_name", "ai_tool", "url", "entry_url", "raw_output_path"],
        )
        writer.writeheader()
        for item in pack["prompts"]:
            writer.writerow(
                {
                    "prompt_id": item["prompt_id"],
                    "game_id": item["game_id"],
                    "game_name": item["game_name"],
                    "ai_tool": item["ai_tool"],
                    "url": item["url"],
                    "entry_url": item.get("entry_url", ""),
                    "raw_output_path": item["raw_output_path"],
                }
            )


def build_pack(args: argparse.Namespace) -> dict[str, Any]:
    games = read_spreadsheet(Path(args.game_list))
    if args.game_limit:
        games = games[: args.game_limit]
    tools = [item.strip() for item in args.tools.split(",") if item.strip()]
    unknown = [tool for tool in tools if tool not in AI_TOOLS]
    if unknown:
        raise ValueError(f"Unknown AI tools: {', '.join(unknown)}")

    end = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start = end - timedelta(days=args.lookback_days - 1)
    template = load_template(Path(args.template) if args.template else None)
    prompts = []
    for game in games:
        for tool in tools:
            prompt_id = f"{game['game_id']}_{slugify(tool)}"
            raw_name = f"{game['game_id']}_{slugify(game['game_name'])}_{slugify(tool)}.json"
            info = AI_TOOLS[tool]
            prompts.append(
                {
                    "prompt_id": prompt_id,
                    "game_id": game["game_id"],
                    "game_name": game["game_name"],
                    "aliases": game.get("aliases", []),
                    "ai_tool": tool,
                    "url": info["url"],
                    "entry_url": info.get("entry_url", ""),
                    "entry_mode": info.get("entry_mode", "direct"),
                    "platform_focus": info["platform_focus"],
                    "time_range": f"{start.isoformat()} 至 {end.isoformat()}",
                    "raw_output_path": f"raw/{raw_name}",
                    "prompt": prompt_with_automation_marker(
                        prompt_id,
                        args.run_id,
                        render_prompt(template, game, tool, start.isoformat(), end.isoformat(), args.max_items),
                    ),
                }
            )

    return {
        "run_id": args.run_id,
        "created_at": date.today().isoformat(),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "lookback_days": args.lookback_days,
        "max_items": args.max_items,
        "tools": tools,
        "game_count": len(games),
        "prompt_count": len(prompts),
        "games": games,
        "prompts": prompts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list", help="Path to .xlsx/.xls/.csv/.tsv game list")
    parser.add_argument("--tools", default=",".join(DEFAULT_TOOLS))
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--game-limit", type=int, default=0, help="Only include the first N games from the list")
    parser.add_argument("--run-id", default=f"game_polling_{date.today().isoformat().replace('-', '')}")
    parser.add_argument("--template", default="")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir or Path.cwd() / "daily_ai_outputs" / args.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(exist_ok=True)

    pack = build_pack(args)
    game_list_path = output_dir / "game_list.json"
    prompt_pack_path = output_dir / "prompt_pack.json"
    game_list_path.write_text(json.dumps({"games": pack["games"], "count": pack["game_count"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompt_pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_ai, by_game = write_grouped_markdown(pack, output_dir)
    write_manifest(pack, output_dir / "prompt_manifest.csv")

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "game_list": str(game_list_path),
                "prompt_pack": str(prompt_pack_path),
                "prompts_by_ai": str(by_ai),
                "prompts_by_game": str(by_game),
                "games": pack["game_count"],
                "prompts": pack["prompt_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
