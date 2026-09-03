#!/usr/bin/env python3
"""Prepare a 3-day company daily intelligence run folder."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def write_runbook(run_dir: Path, prompt_pack: Path, prompt_md: Path, raw_dir: Path, structured_path: Path, report_path: Path, args: argparse.Namespace) -> None:
    lines = [
        "# Company Daily Intelligence Runbook",
        "",
        "## Purpose",
        "",
        "Use logged-in Web AI pages to collect URL-backed evidence for a 3-day 米哈游 / 库洛 / 二游大盘 daily report.",
        "",
        "## Files",
        "",
        f"- Prompt pack JSON: `{prompt_pack}`",
        f"- Prompt markdown: `{prompt_md}`",
        f"- Raw output directory: `{raw_dir}`",
        f"- Robust structured output: `{structured_path}`",
        f"- HTML report: `{report_path}`",
        "",
        "## Browser Steps",
        "",
        "1. Open the required Web AI pages in the Codex in-app browser or WorkBuddy external browser.",
        "2. The operator logs in manually. Do not request, store, export, or print credentials, cookies, tokens, or browser profile data.",
        "3. Submit each prompt from `prompt_pack.md` to the matching AI page.",
        "4. Save each full reply as `raw/<prompt_id>.json` using the evidence/pending_leads contract in the prompt.",
        "5. Keep this run separate from old `codex_1game_*` or `game_polling_*` outputs; do not copy historical raw files into this `raw/` folder unless the operator explicitly requests comparison.",
        "6. Do not bypass login, CAPTCHA, 403, paywalls, rate limits, or private groups.",
        "7. Re-render HTML after raw outputs are saved.",
        "",
        "## Re-render Command",
        "",
        "```powershell",
        " ".join(
            [
                "python",
                str(SCRIPT_DIR / "robust_structure_raw.py"),
                str(raw_dir),
                "--output",
                str(structured_path),
                "--report-date",
                args.end_date,
                "--lookback-days",
                str(args.lookback_days),
            ]
        ),
        "```",
        "",
        "```powershell",
        " ".join(
            [
                "python",
                str(SCRIPT_DIR / "render_company_daily_report.py"),
                str(structured_path),
                "--output",
                str(report_path),
                "--report-date",
                args.end_date,
                "--lookback-days",
                str(args.lookback_days),
                "--allow-no-url-evidence",
            ]
        ),
        "```",
        "",
        "## Daily Default",
        "",
        f"- Lookback days: {args.lookback_days}",
        "- Core scope: 米哈游, 库洛, 二游大盘.",
        "- Product matrix includes 战双帕弥什 and the full 米哈游 product list supplied by the operator.",
        "- Layer 1 uses all selected AI tools for company/market fast scan.",
        "- Layer 2 adds community deep-dive prompts for 点点 and 知乎直答 by default, so 小红书 and 知乎 can better reflect player tendency.",
        "- Robust preview mode: save raw replies first, run `robust_structure_raw.py`, then render. Do not block the report only because Grok/Qianwen returned Markdown or prose.",
    ]
    (run_dir / "runbook.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"company_daily_{date.today():%Y%m%d}")
    parser.add_argument("--output-root", default="daily_ai_outputs")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--tools", default="元宝,豆包,文心一言,千问,点点,知乎直答,Gemini,Grok")
    parser.add_argument("--max-mihoyo-items", type=int, default=10)
    parser.add_argument("--max-kuro-items", type=int, default=6)
    parser.add_argument("--max-market-items", type=int, default=10)
    parser.add_argument("--community-deep-dive-tools", default="点点,知乎直答")
    parser.add_argument("--max-community-items", type=int, default=12)
    parser.add_argument("--skip-community-deep-dive", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.output_root) / args.run_id
    raw_dir = run_dir / "raw"
    reports_dir = run_dir / "reports"
    structured_dir = run_dir / "structured"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    structured_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    run(
        [
            python,
            str(SCRIPT_DIR / "build_company_daily_pack.py"),
            "--run-id",
            args.run_id,
            "--output-dir",
            str(run_dir),
            "--end-date",
            args.end_date,
            "--lookback-days",
            str(args.lookback_days),
            "--tools",
            args.tools,
            "--max-mihoyo-items",
            str(args.max_mihoyo_items),
            "--max-kuro-items",
            str(args.max_kuro_items),
            "--max-market-items",
            str(args.max_market_items),
            "--community-deep-dive-tools",
            args.community_deep_dive_tools,
            "--max-community-items",
            str(args.max_community_items),
        ]
        + (["--skip-community-deep-dive"] if args.skip_community_deep_dive else [])
    )

    report_path = reports_dir / "index.html"
    structured_path = structured_dir / "robust_structured.json"
    run(
        [
            python,
            str(SCRIPT_DIR / "robust_structure_raw.py"),
            str(raw_dir),
            "--output",
            str(structured_path),
            "--report-date",
            args.end_date,
            "--lookback-days",
            str(args.lookback_days),
        ]
    )
    run(
        [
            python,
            str(SCRIPT_DIR / "render_company_daily_report.py"),
            str(structured_path),
            "--output",
            str(report_path),
            "--report-date",
            args.end_date,
            "--lookback-days",
            str(args.lookback_days),
            "--allow-no-url-evidence",
        ]
    )

    prompt_pack = run_dir / "prompt_pack.json"
    prompt_md = run_dir / "prompt_pack.md"
    write_runbook(run_dir, prompt_pack, prompt_md, raw_dir, structured_path, report_path, args)

    summary = {
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "prompt_pack": str(prompt_pack),
        "prompt_markdown": str(prompt_md),
        "raw_dir": str(raw_dir),
        "structured_output": str(structured_path),
        "report_html": str(report_path),
        "runbook": str(run_dir / "runbook.md"),
        "lookback_days": args.lookback_days,
        "tools": [item.strip() for item in args.tools.split(",") if item.strip()],
        "community_deep_dive_tools": [] if args.skip_community_deep_dive else [item.strip() for item in args.community_deep_dive_tools.split(",") if item.strip()],
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
