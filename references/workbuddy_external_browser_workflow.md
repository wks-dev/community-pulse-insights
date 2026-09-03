# WorkBuddy External Browser Workflow

Use this reference when the operator wants to run `game-community-ai-intelligence` in WorkBuddy instead of Codex.

## Positioning

This is the WorkBuddy execution path for the same Skill logic:

```text
game list / task
→ prompt_pack.json
→ workbuddy_job.json
→ WorkBuddy external browser submits prompts to logged-in Web AI pages
→ raw AI outputs
→ per-game HTML + combined HTML report
```

Codex's in-app browser is not required in this mode. WorkBuddy should use its own external browser / agent-browser capability.

## Required Files

Generate these files with:

```bash
python scripts/run_game_polling_pipeline.py <game_list.xlsx> --run-id <run_id> --output-root <output_root>
```

The command writes:

- `prompt_pack.json`: all prompts, one prompt per game per AI tool.
- `workbuddy_job.json`: WorkBuddy external-browser job specification.
- `workbuddy_queue.csv`: flat queue for monitoring progress.
- `workbuddy_runbook.md`: human-readable WorkBuddy execution guide.
- `raw/`: target directory for AI replies.
- `reports/`: target directory for HTML output.

To build only the WorkBuddy job from an existing prompt pack:

```bash
python scripts/build_workbuddy_job.py daily_ai_outputs/<run_id>/prompt_pack.json --output-dir daily_ai_outputs/<run_id>
```

## Login And Access Rules

- The operator must manually log in to each AI site in WorkBuddy's external browser.
- WorkBuddy must not request, store, export, or print credentials, OTPs, cookies, tokens, local storage, or browser profile files.
- WorkBuddy must not bypass login, CAPTCHA, 403, paywalls, private groups, rate limits, or other access controls.
- If a page is not accessible, save the limitation and continue with other tools.
- No fixed screen coordinates. Prefer DOM, accessibility role/name, placeholder, `contenteditable`, visible text, and stable attributes.

## Default Web AI Matrix

| AI tool | Entry | Focus |
|---|---|---|
| 元宝 | `https://yuanbao.tencent.com/` | 微信生态、公众号、新闻、腾讯系内容、中文网页 |
| 豆包 | `https://www.doubao.com/` | 抖音、微博、B站、中文网页、新闻、TikTok线索 |
| 文心一言 | `https://wenxin.baidu.com/` | 百度、中文网页、新闻、贴吧、百度知道/百科生态 |
| 千问 | `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5` | 中文网页、新闻、公开搜索、社区线索；千问只是执行工具，不是检索对象 |
| 点点 | `https://www.xiaohongshu.com/ai_chat` | 小红书、种草内容、社媒讨论 |
| 知乎直答 | `https://zhida.zhihu.com/` | 知乎问答、争议复盘、中文网页 |
| Gemini | `https://gemini.google.com/app` | 全球公开网页、YouTube、Instagram |
| Grok | `https://grok.com/` | X/Twitter、全球社媒、实时公开讨论 |

## Special Entry Rules

### 点点 / 小红书

- Preferred entry is `https://www.xiaohongshu.com/ai_chat`.
- If WorkBuddy needs a source-platform context, open `https://www.xiaohongshu.com/` first, confirm login, then enter 点点 / AI chat.
- Valid final hosts include `www.xiaohongshu.com` and `diandian.xiaohongshu.com`.
- Do not treat title-only 小红书 summaries as evidence. `xiaohongshu.com` or `xhslink.com` URLs are required for core evidence.

### 文心一言

- Correct entry is `https://wenxin.baidu.com/`.
- Do not use `https://wenxin.baidu.com/home` as the target chat entry.
- Exclude product intro pages and special tools such as 魔法图片、写作帮手、放心写, or app download pages.
- The correct target is the ordinary text conversation/search page.

### 千问

- Correct entry is `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`.
- Normal page signals include `千问-阿里 AI 助手`, `Qwen`, `向千问提问`, and `新建对话`.
- Prefer the ordinary text input identified by `[role="textbox"][contenteditable="true"]`.
- Do not use `API 服务`, downloads, PPT creation, image/video generation, translation, code, or other special-tool pages as the target chat entry.
- Treat `千问`, `Qwen`, `通义千问`, and `阿里 AI 助手` as execution-page identity labels only. If the reply only describes these AI products, API pages, downloads, or model features, mark `prompt_drift`, skip `evidence` and game-community `pending_leads`, then retry once with actual game/company keywords.

### 知乎直答

- The ordinary search/question page must not contain `/repositories/`.
- If the page says `订阅知识库后即可进行提问`, it is the wrong page.
- Enter the left-side 搜索 route before submitting prompts.

## Queue Execution Contract

For each item in `workbuddy_job.json.queue`:

1. Open or reuse the AI page for `ai_tool`.
2. Verify login and page identity. Stop that item if the page is login, CAPTCHA, 403, product intro, repository, or special-tool page.
3. Locate the main input box by DOM/accessibility/placeholder/contenteditable.
4. Clear old content with click, select-all, delete/backspace, then verify the input is empty.
5. Insert `prompt`, read back the input, and confirm the prompt is not appended to old content.
6. Send through a confirmed send button or platform-confirmed keyboard shortcut.
7. Confirm the new user message appears.
8. Wait for the corresponding new AI reply after that user message.
9. Wait until streaming stops.
10. Save the full reply to `raw_output_path`.
11. Keep URL-backed findings in `evidence`; keep no-URL or unverifiable findings in `pending_leads`.

## Raw Output Contract

Each raw file should be JSON when possible:

```json
{
  "prompt_id": "game_001_豆包",
  "game_id": "game_001",
  "game_name": "原神",
  "ai_tool": "豆包",
  "submitted_at": "2026-07-24T09:05:00+08:00",
  "retrieved_at": "2026-07-24T09:06:30+08:00",
  "response_text": "full visible AI reply text",
  "evidence": [],
  "pending_leads": [],
  "limitations": []
}
```

If the AI returns Markdown or mixed text, save it under `response_text` and let the merge/render stage extract URL-backed evidence.

## HTML Rendering

After WorkBuddy saves raw outputs, render reports with:

```bash
python scripts/render_game_polling_reports.py daily_ai_outputs/<run_id>/game_list.json daily_ai_outputs/<run_id>/raw --output-dir daily_ai_outputs/<run_id>/reports
```

Expected output:

- `reports/index.html`: combined report for all games.
- `reports/games/<game_id>_<game_name>.html`: one HTML report per game.

## Recommended First Run

Before polling the full list, run only the first game across the selected AI tools. Confirm that each site can:

- locate input;
- clear old text;
- submit the prompt;
- confirm the user message;
- extract the new reply;
- save raw JSON;
- render HTML.

Then run the full queue.
