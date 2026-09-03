# Playwright Web AI Runner

Use `scripts/run_web_ai_with_playwright.js` only when the user explicitly wants standalone Playwright/local Chrome execution. In Codex, prefer `references/in_app_browser_polling_workflow.md`; in WorkBuddy, prefer `references/workbuddy_external_browser_workflow.md`.

## Prerequisites

- Google Chrome is installed.
- Node.js can run the script. In Codex Desktop, use the bundled Node runtime when system `node` is unavailable.
- A dedicated browser profile is available. Default: `.pw-ai-profile` in the current project.
- The user has manually logged in to each AI tool inside the dedicated profile.

## Login Check

Run this before submitting prompts:

```powershell
node scripts/run_web_ai_with_playwright.js --mode login-check --tools 豆包,元宝,文心一言,千问,点点,知乎直答,Gemini,Grok --hold-ms 15000
```

The script opens each site, waits briefly, saves `daily_ai_outputs/playwright_login_check.json`, and closes the browser context.

## Submit Prompt Batches

After generating `prompt_pack.json`, run:

```powershell
node scripts/run_web_ai_with_playwright.js --submit --prompt-pack daily_ai_outputs/<run_id>/prompt_pack.json --output-dir daily_ai_outputs/<run_id>/raw --limit 2
```

Remove `--limit` only after a small batch succeeds.

For 点点 + 小红书 prompt items, the prompt pack should include:

```json
{
  "ai_tool": "点点",
  "url": "https://www.xiaohongshu.com/ai_chat",
  "entry_url": "https://www.xiaohongshu.com/",
  "entry_mode": "open_entry_then_launch_ai"
}
```

The runner opens 小红书 first, then enters 点点 from the same tab/context. If the 小红书 entry page is blocked by login, CAPTCHA, 403, or other access controls, the run must record the limitation and must not bypass it.

## Output

- Raw page text: `daily_ai_outputs/<prompt_id>.md`
- Parsed JSON when available: `daily_ai_outputs/<prompt_id>.json`
- Summary: `daily_ai_outputs/playwright_submit_summary.json`

Merge parsed JSON files with:

```powershell
python scripts/merge_daily_ai_outputs.py daily_ai_outputs/*.json --output daily_evidence.json
```

Then render HTML with:

```powershell
python scripts/render_daily_game_report.py daily_evidence.json --output daily_game_report.html
```

## Safety

- Default mode does not submit anything.
- `--submit` is required for prompt submission.
- Do not automate CAPTCHA, hidden APIs, private groups, paywalled pages, or 403 pages.
- The runner does not use coordinate click fallback by default; use `--allow-coordinate-fallback true` only for manual debugging, not for evidence runs.
- Web AI results without URLs stay as `pending_leads` or secondary observations.
