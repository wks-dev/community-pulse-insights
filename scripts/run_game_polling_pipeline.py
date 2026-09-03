#!/usr/bin/env python3
"""Run the game-list polling pipeline: prompts, optional Web AI submit, HTML reports."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list", help="Path to game list .xlsx/.xls/.csv/.tsv")
    parser.add_argument("--run-id", default=f"game_polling_{date.today().isoformat().replace('-', '')}")
    parser.add_argument("--output-root", default="daily_ai_outputs")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--game-limit", type=int, default=0, help="Only include the first N games from the list")
    parser.add_argument("--tools", default="元宝,豆包,文心一言,千问,点点,知乎直答,Gemini,Grok")
    parser.add_argument("--submit", action="store_true", help="Submit prompts to Web AI with Playwright")
    parser.add_argument("--node", default=os.environ.get("NODE_EXE", "node"))
    parser.add_argument("--profile-dir", default="")
    parser.add_argument("--chrome-path", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--response-wait-ms", type=int, default=120000)
    parser.add_argument("--skip-workbuddy-job", action="store_true", help="Do not write WorkBuddy external-browser job files")
    args = parser.parse_args()

    run_dir = Path(args.output_root) / args.run_id
    raw_dir = run_dir / "raw"
    reports_dir = run_dir / "reports"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(exist_ok=True)

    python = sys.executable
    prompt_pack = run_dir / "prompt_pack.json"
    game_list_json = run_dir / "game_list.json"

    run(
        [
            python,
            str(SCRIPT_DIR / "build_game_polling_pack.py"),
            args.game_list,
            "--tools",
            args.tools,
            "--lookback-days",
            str(args.lookback_days),
            "--end-date",
            args.end_date,
            "--max-items",
            str(args.max_items),
            "--game-limit",
            str(args.game_limit),
            "--run-id",
            args.run_id,
            "--output-dir",
            str(run_dir),
        ]
    )

    workbuddy_job = ""
    if not args.skip_workbuddy_job:
        run(
            [
                python,
                str(SCRIPT_DIR / "build_workbuddy_job.py"),
                str(prompt_pack),
                "--output-dir",
                str(run_dir),
            ]
        )
        workbuddy_job = str(run_dir / "workbuddy_job.json")

    submit_summary = ""
    if args.submit:
        command = [
            args.node,
            str(SCRIPT_DIR / "run_web_ai_with_playwright.js"),
            "--submit",
            "--prompt-pack",
            str(prompt_pack),
            "--output-dir",
            str(raw_dir),
            "--response-wait-ms",
            str(args.response_wait_ms),
        ]
        if args.profile_dir:
            command.extend(["--profile-dir", args.profile_dir])
        if args.chrome_path:
            command.extend(["--chrome-path", args.chrome_path])
        if args.tools:
            command.extend(["--tools", args.tools])
        if args.limit:
            command.extend(["--limit", str(args.limit)])
        run(command)
        submit_summary = str(raw_dir / "playwright_submit_summary.json")

    run(
        [
            python,
            str(SCRIPT_DIR / "render_game_polling_reports.py"),
            str(game_list_json),
            str(raw_dir),
            "--output-dir",
            str(reports_dir),
            "--report-date",
            args.end_date,
        ]
    )

    summary = {
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "game_list_json": str(game_list_json),
        "prompt_pack": str(prompt_pack),
        "raw_dir": str(raw_dir),
        "reports_dir": str(reports_dir),
        "index_html": str(reports_dir / "index.html"),
        "submit_summary": submit_summary,
        "submitted": args.submit,
        "workbuddy_job": workbuddy_job,
        "workbuddy_runbook": str(run_dir / "workbuddy_runbook.md") if workbuddy_job else "",
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
