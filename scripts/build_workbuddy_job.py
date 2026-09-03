#!/usr/bin/env python3
"""Build WorkBuddy external-browser job files from a prompt_pack.json."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any


SITE_RULES: dict[str, dict[str, Any]] = {
    "元宝": {
        "entry_url": "https://yuanbao.tencent.com/",
        "chat_url": "https://yuanbao.tencent.com/chat/naQivTmsDa",
        "identity": ["腾讯元宝", "新对话", "有什么可以帮你"],
        "platform_focus": "微信生态、公众号、新闻、腾讯系内容、中文网页",
    },
    "豆包": {
        "entry_url": "https://www.doubao.com/",
        "chat_url": "https://www.doubao.com/chat/?channel=browser_landing_page",
        "identity": ["豆包", "新对话", "有什么可以帮你"],
        "platform_focus": "抖音、微博、B站、中文网页、新闻、TikTok线索",
    },
    "文心一言": {
        "entry_url": "https://wenxin.baidu.com/",
        "chat_url": "https://wenxin.baidu.com/",
        "identity": ["新对话", "自动模式", "有什么可以帮你"],
        "exclude": ["wenxin.baidu.com/home", "魔法图片", "写作帮手", "放心写", "APP下载"],
        "platform_focus": "百度、中文网页、新闻、贴吧、百度知道/百科生态",
    },
    "千问": {
        "entry_url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "chat_url": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
        "identity": ["千问-阿里 AI 助手", "Qwen", "向千问提问", "新建对话"],
        "exclude": ["API 服务", "下载电脑端", "PPT创作", "AI生图", "AI生视频", "翻译", "代码"],
        "platform_focus": "中文网页、新闻、公开搜索、跨平台社区线索；千问只是执行工具，不是检索对象",
        "prompt_guardrail": "如果结果只返回千问/Qwen/通义千问/阿里AI助手产品介绍，视为检索漂移，必须换用游戏名/公司名重试，不要保存为舆情线索。",
    },
    "点点": {
        "entry_url": "https://www.xiaohongshu.com/",
        "chat_url": "https://www.xiaohongshu.com/ai_chat",
        "entry_mode": "open_xiaohongshu_then_ai_chat",
        "identity": ["点点", "想探索些什么", "ai_chat"],
        "allowed_hosts": ["www.xiaohongshu.com", "diandian.xiaohongshu.com"],
        "platform_focus": "小红书、种草内容、社媒讨论；优先返回 xiaohongshu.com 或 xhslink.com 证据",
    },
    "知乎直答": {
        "entry_url": "https://zhida.zhihu.com/",
        "chat_url": "https://zhida.zhihu.com/",
        "identity": ["搜索", "用提问发现世界"],
        "exclude": ["/repositories/", "订阅知识库后即可进行提问"],
        "platform_focus": "知乎问答、争议复盘、中文网页",
    },
    "Gemini": {
        "entry_url": "https://gemini.google.com/app",
        "chat_url": "https://gemini.google.com/app",
        "identity": ["Gemini"],
        "platform_focus": "全球公开网页、YouTube、Instagram",
    },
    "Grok": {
        "entry_url": "https://grok.com/",
        "chat_url": "https://grok.com/",
        "identity": ["Grok"],
        "platform_focus": "X/Twitter、全球社媒、实时公开讨论",
    },
}


RAW_OUTPUT_CONTRACT = {
    "prompt_id": "string",
    "game_id": "string",
    "game_name": "string",
    "ai_tool": "string",
    "submitted_at": "ISO-8601 datetime or empty",
    "retrieved_at": "ISO-8601 datetime",
    "response_text": "full visible AI reply text",
    "evidence": [
        {
            "title": "string",
            "url": "string, required for evidence",
            "published_at": "string",
            "source_platform": "string",
            "event_summary": "string",
            "player_sentiment": "positive / negative / neutral / mixed",
            "player_intent": "string",
            "supported_claim": "string",
            "confidence": "low / medium / high",
        }
    ],
    "pending_leads": [
        {
            "title": "string",
            "reason": "no URL / blocked / needs verification",
            "summary": "string",
        }
    ],
    "limitations": ["string"],
}


def resolve_run_path(run_dir: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((run_dir / path).resolve())


def build_job(prompt_pack_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    pack = json.loads(prompt_pack_path.read_text(encoding="utf-8"))
    run_dir = prompt_pack_path.resolve().parent
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir
    raw_dir = Path(args.raw_dir).resolve() if args.raw_dir else output_dir / "raw"
    reports_dir = Path(args.reports_dir).resolve() if args.reports_dir else output_dir / "reports"
    queue_items = []
    prompts = pack.get("prompts", [])
    if args.limit:
        prompts = prompts[: args.limit]

    for item in prompts:
        ai_tool = item["ai_tool"]
        rule = SITE_RULES.get(ai_tool, {})
        raw_output_path = resolve_run_path(output_dir, item.get("raw_output_path", f"raw/{item['prompt_id']}.json"))
        queue_items.append(
            {
                "prompt_id": item["prompt_id"],
                "game_id": item["game_id"],
                "game_name": item["game_name"],
                "ai_tool": ai_tool,
                "entry_url": rule.get("entry_url") or item.get("entry_url") or item.get("url"),
                "chat_url": rule.get("chat_url") or item.get("url"),
                "entry_mode": rule.get("entry_mode") or item.get("entry_mode", "direct"),
                "platform_focus": item.get("platform_focus") or rule.get("platform_focus", ""),
                "time_range": item.get("time_range", ""),
                "prompt": item["prompt"],
                "raw_output_path": raw_output_path,
                "fallback_policy": item.get("fallback_policy", ""),
                "fallback_prompt_id": item.get("fallback_prompt_id", ""),
                "fallback_prompt": item.get("fallback_prompt", ""),
                "fallback_raw_output_path": resolve_run_path(output_dir, item["fallback_raw_output_path"]) if item.get("fallback_raw_output_path") else "",
                "status": "pending",
            }
        )

    return {
        "job_type": "game_community_ai_intelligence_workbuddy_external_browser",
        "run_id": pack.get("run_id") or output_dir.name,
        "created_at": date.today().isoformat(),
        "executor": {
            "surface": "WorkBuddy external browser / agent-browser",
            "login_policy": "manual_login_only",
            "credential_policy": "do_not_request_store_export_or_print_credentials_cookies_tokens_or_browser_profiles",
            "coordinate_policy": "do_not_use_fixed_screen_coordinates",
            "access_policy": "do_not_bypass_login_captcha_403_paywall_rate_limits_or_private_groups",
        },
        "paths": {
            "prompt_pack": str(prompt_pack_path.resolve()),
            "game_list_json": str((output_dir / "game_list.json").resolve()),
            "raw_dir": str(raw_dir),
            "reports_dir": str(reports_dir),
            "index_html": str(reports_dir / "index.html"),
        },
        "render_command": [
            "python",
            "scripts/render_game_polling_reports.py",
            str((output_dir / "game_list.json").resolve()),
            str(raw_dir),
            "--output-dir",
            str(reports_dir),
            "--report-date",
            pack.get("end_date", date.today().isoformat()),
        ],
        "site_rules": SITE_RULES,
        "raw_output_contract": RAW_OUTPUT_CONTRACT,
        "automation_steps": [
            "Open or reuse the external browser page for the queue item's ai_tool.",
            "If not logged in, pause and ask the operator to log in manually. Do not handle credentials.",
            "Verify the page is the normal chat/search page and not a login, CAPTCHA, 403, product intro, repository, or special-tool page.",
            "Locate the main prompt input by DOM, accessibility role/name, placeholder, or contenteditable; do not use fixed coordinates.",
            "Clear old content, input the prompt, then read the input back to confirm the prompt is present and not appended to previous content.",
            "Send through a confirmed send button or platform-confirmed keyboard shortcut.",
            "Confirm a new user message appears for this prompt before waiting for the AI reply.",
            "Wait until the corresponding new AI reply finishes streaming, extract the full reply, and save it to raw_output_path.",
            "Keep URL-backed items in evidence and URL-less summaries in pending_leads.",
            "If an AI reply focuses on the AI tool itself instead of the requested game/company/community target, mark the item as prompt_drift and retry once with the game/company names only.",
            "For Qianwen, Grok, Gemini, and DianDian, use fallback_prompt once when send confirmation fails, prompt drift appears, or the reply is useful prose but not strict JSON.",
            "Always save the full raw reply first; later run robust structuring before rendering so Markdown/prose can still become pending leads or URL-backed evidence.",
            "After queue completion, run render_command to generate per-game HTML and the combined index.html.",
        ],
        "queue": queue_items,
        "queue_count": len(queue_items),
        "game_count": pack.get("game_count", 0),
        "tools": pack.get("tools", []),
    }


def write_queue_csv(job: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "prompt_id",
                "game_id",
                "game_name",
                "ai_tool",
                "entry_url",
                "chat_url",
                "entry_mode",
                "raw_output_path",
                "status",
            ],
        )
        writer.writeheader()
        for item in job["queue"]:
            writer.writerow({key: item.get(key, "") for key in writer.fieldnames or []})


def write_runbook(job: dict[str, Any], path: Path) -> None:
    lines = [
        "# WorkBuddy External Browser Runbook",
        "",
        "## Purpose",
        "",
        "Use WorkBuddy's external browser or agent-browser to submit the saved game-intelligence prompts to logged-in Web AI pages, save raw replies, then render HTML reports.",
        "",
        "## Preconditions",
        "",
        "- The operator manually logs in to each required AI site in WorkBuddy's browser.",
        "- WorkBuddy must not request, store, export, or print passwords, OTPs, cookies, tokens, local storage, or browser profile files.",
        "- WorkBuddy must not bypass login, CAPTCHA, 403, paywalls, private groups, or rate limits.",
        "- Use DOM, accessibility, placeholder, contenteditable, or stable attributes. Do not use fixed screen coordinates.",
        "",
        "## Files",
        "",
        f"- Prompt pack: `{job['paths']['prompt_pack']}`",
        f"- Raw output directory: `{job['paths']['raw_dir']}`",
        f"- Combined HTML: `{job['paths']['index_html']}`",
        "",
        "## Execution Contract",
        "",
        "For every queue item in `workbuddy_job.json`:",
        "",
        "1. Open `entry_url` or reuse the already logged-in page for `ai_tool`.",
        "2. Verify the page is a normal chat/search page for that AI tool.",
        "3. Clear the input box and verify it is empty.",
        "4. Insert the prompt and read it back before sending.",
        "5. Send the prompt and confirm a new user message appears.",
        "6. Wait for the corresponding AI reply to finish streaming.",
        "7. Save the full visible reply to `raw_output_path` using the raw output contract.",
        "8. Put URL-backed findings into `evidence`; put no-URL or blocked items into `pending_leads`.",
        "",
        "## Render HTML",
        "",
        "After raw outputs are saved, run:",
        "",
        "```powershell",
        " ".join(job["render_command"]),
        "```",
        "",
        "## Site Notes",
        "",
    ]
    for site, rule in job["site_rules"].items():
        lines.extend(
            [
                f"### {site}",
                "",
                f"- Entry URL: `{rule.get('entry_url', '')}`",
                f"- Chat URL: `{rule.get('chat_url', '')}`",
                f"- Focus: {rule.get('platform_focus', '')}",
                f"- Identity hints: {', '.join(rule.get('identity', []))}",
            ]
        )
        if rule.get("exclude"):
            lines.append(f"- Exclude: {', '.join(rule['exclude'])}")
        if rule.get("allowed_hosts"):
            lines.append(f"- Allowed hosts: {', '.join(rule['allowed_hosts'])}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt_pack", help="Path to prompt_pack.json")
    parser.add_argument("--output-dir", default="", help="Run directory; defaults to prompt_pack parent")
    parser.add_argument("--raw-dir", default="")
    parser.add_argument("--reports-dir", default="")
    parser.add_argument("--limit", type=int, default=0, help="Only include the first N prompts")
    args = parser.parse_args()

    prompt_pack_path = Path(args.prompt_pack)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else prompt_pack_path.resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(exist_ok=True)

    job = build_job(prompt_pack_path, args)
    job_path = output_dir / "workbuddy_job.json"
    queue_path = output_dir / "workbuddy_queue.csv"
    runbook_path = output_dir / "workbuddy_runbook.md"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_queue_csv(job, queue_path)
    write_runbook(job, runbook_path)

    print(
        json.dumps(
            {
                "workbuddy_job": str(job_path),
                "workbuddy_queue": str(queue_path),
                "workbuddy_runbook": str(runbook_path),
                "queue_count": job["queue_count"],
                "raw_dir": job["paths"]["raw_dir"],
                "index_html": job["paths"]["index_html"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
