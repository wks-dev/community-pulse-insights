# Game-List Polling Workflow

Use this reference when a user provides a game list and wants each game queried through multiple Web AI tools.

## Pipeline

1. Normalize the workbook with `scripts/load_game_list.py`.
2. Build a prompt pack with `scripts/build_game_polling_pack.py`.
3. Submit each prompt to the selected AI tools. Save raw responses before any merge.
4. Normalize and merge URL-backed evidence. Keep URL-less or unverifiable items in `pending_leads`.
5. Render reports with `scripts/render_game_polling_reports.py`.

Inside Codex, prefer the in-app browser workflow: the operator manually logs in to the AI pages, Codex claims those already opened and logged-in tabs, submits prompts, saves raw outputs, and renders reports. Read `references/in_app_browser_polling_workflow.md`.

Inside WorkBuddy, use the external-browser workflow: the operator manually logs in to the AI pages in WorkBuddy's browser, WorkBuddy reads `workbuddy_job.json`, submits prompts through its own agent-browser, saves raw outputs, and renders reports. Read `references/workbuddy_external_browser_workflow.md`.

Use `scripts/run_game_polling_pipeline.py` when an operator wants prompt generation and report rendering in one command. The command writes WorkBuddy handoff files by default: `workbuddy_job.json`, `workbuddy_queue.csv`, and `workbuddy_runbook.md`. Its `--submit` mode uses the optional Playwright runner and is intended for standalone Chrome or non-Codex/non-WorkBuddy environments.

## Default Polling Matrix

Default tools are:

- 元宝
- 豆包
- 文心一言
- 千问
- 点点
- 知乎直答
- Gemini
- Grok

Default prompt granularity is one game per AI, so a 44-game list creates `44 * 8 = 352` prompts.

## Output Layout

Recommended run directory:

```text
daily_ai_outputs/<run_id>/
├── game_list.json
├── prompt_pack.json
├── workbuddy_job.json
├── workbuddy_queue.csv
├── workbuddy_runbook.md
├── prompts_by_ai/
│   ├── 元宝.md
│   └── ...
├── prompts_by_game/
│   ├── game_001_原神.md
│   └── ...
├── raw/
│   ├── game_001_原神_元宝.json
│   └── ...
└── reports/
    ├── index.html
    └── games/
        ├── game_001_原神.html
        └── ...
```

## Evidence Rules

- `evidence` items must have a non-empty URL.
- `pending_leads` may contain AI-only summaries, no-URL hints, blocked pages, or items that need later verification.
- A combined report must never claim full-community coverage unless a real API/export supports it.
- The report must display sample range, AI tools used, access limitations, and confidence.

## WorkBuddy / ChatGPT Packaging

When moving this Skill to WorkBuddy, ChatGPT, or another agent platform, preserve these files:

- `SKILL.md`
- `references/universal_game_polling_prompt.md`
- `references/game_list_polling_workflow.md`
- `references/in_app_browser_polling_workflow.md`
- `references/workbuddy_external_browser_workflow.md`
- `references/evidence_schema.md`
- `references/tagging_schema.md`
- `scripts/load_game_list.py`
- `scripts/build_game_polling_pack.py`
- `scripts/build_workbuddy_job.py`
- `scripts/run_game_polling_pipeline.py`
- `scripts/run_web_ai_with_playwright.js`
- `scripts/render_game_polling_reports.py`

If the target platform is WorkBuddy, use `workbuddy_job.json` as the primary handoff artifact. If the target platform cannot run scripts, use `prompt_pack.json` as a plain prompt handoff artifact and let the platform submit prompts through its own browser or workflow runner.

## WorkBuddy External Browser Mode

WorkBuddy should not treat this Skill as Codex-only. In WorkBuddy:

1. Generate `prompt_pack.json` and `workbuddy_job.json`.
2. Ask the operator to log in to 元宝、豆包、文心一言、千问、点点、知乎直答、Gemini、Grok in WorkBuddy's external browser.
3. WorkBuddy reads `workbuddy_job.json.queue`.
4. WorkBuddy submits each prompt with its agent-browser, using DOM/accessibility/placeholder/contenteditable locators instead of fixed screen coordinates.
5. WorkBuddy saves every AI reply to the `raw_output_path` specified by the queue item.
6. WorkBuddy runs `scripts/render_game_polling_reports.py` to generate one HTML per game plus the combined `index.html`.

The Codex in-app browser instructions do not apply in this mode.
