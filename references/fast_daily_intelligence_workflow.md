# Fast Daily Intelligence Workflow

Use this workflow for a 3-day 二游日报 focused on 米哈游, 库洛, and the broader 二游 market.

## Why This Exists

The full `game x AI matrix` polling mode is useful for deep audits, but it is too slow for a daily report. The fast daily mode sends one compact company/market prompt to each selected Web AI tool. Each prompt covers:

1. 米哈游 product matrix.
2. 库洛 product matrix.
3. 二游大盘 trends.

This reduces a daily run from dozens or hundreds of prompts to roughly 7-9 prompts while still asking each Web AI to return URL-backed evidence.

## Separation From Previous Modes

This mode may reuse the skill's browser, evidence, and HTML conventions, but it is a separate workflow:

- Use run IDs like `company_daily_YYYYMMDD`.
- Save raw replies under that run's own `raw/` folder.
- Render only that run's raw outputs into that run's `reports/index.html`.
- Do not mix in old `codex_1game_*`, `game_polling_*`, or manual test outputs unless the user explicitly asks for historical comparison.
- Keep exhaustive game-list polling for deep audits and weekly baselines.

## Two-Layer Daily Design

Layer 1 is the company/market fast scan. It asks each selected Web AI to search 米哈游, 库洛, and 二游大盘 in one detailed prompt.

Layer 2 is community deep dive. By default it adds:

- 点点: 小红书/女性向/种草/角色消费/回流退坑/抽卡付费 feedback.
- 知乎直答: 知乎争议复盘/竞品比较/玩家信任/运营评价.

Layer 2 exists because community platforms often reflect player tendency better than news-like search results. It should return more concrete opinions, but still obey the URL rule.

## Default Scope

- Time window: recent 7 days for weekly reports; recent 3 days for daily reports.
- Default tools: 元宝, 豆包, 文心一言, 千问, 点点, 知乎直答, Gemini, Grok.
- Default output: one polished HTML weekly or daily report.
- Evidence rule: no URL, no core conclusion.

## Weekly Expanded Scan

For reports where the user expects richer coverage, use weekly mode:

```powershell
python C:\Users\Lenovo\.codex\skills\game-community-ai-intelligence-daily-robust-preview\scripts\build_company_daily_pack.py `
  --output-dir D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs\company_weekly_YYYYMMDD `
  --report-mode weekly `
  --game-list C:\Users\Lenovo\Desktop\二游名单.xlsx
```

Weekly mode keeps the watch matrix as an observation scope, not a full game-by-AI polling queue. It adds `layer2_weekly_expansion` prompts by default for 豆包, Gemini, and Grok. These prompts are specifically for:

- expanding hits across the 40+ watch-matrix games when recent public information exists;
- adding other 二游 and competitor items beyond 米哈游 / 库洛;
- turning sector lenses into real news/community cases rather than static definitions;
- preserving `plain_summary`, `why_watch`, `business_use`, `sector`, `sector_item`, `is_watch_matrix_game`, and `is_key_company`.

The report should show weekly coverage metrics, hit games, sector cases, other 二游/competitor dynamics, source scope, and limitations. URL-less items remain auxiliary samples or pending leads.

## Build Prompt Pack

```powershell
python C:\Users\Lenovo\.codex\skills\game-community-ai-intelligence-daily-robust-preview\scripts\build_company_daily_pack.py `
  --output-dir D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs\company_daily_test `
  --lookback-days 3
```

Outputs:

- `prompt_pack.json`
- `prompt_pack.md`

The default pack contains:

- 8 Layer-1 prompts: 元宝, 豆包, 文心一言, 千问, 点点, 知乎直答, Gemini, Grok.
- 2 Layer-2 prompts: 点点 community deep dive and 知乎直答 community deep dive.

Use `--skip-community-deep-dive` if speed is more important than community detail.

### 40-Game Watch Matrix

For the robust preview company daily report, a workbook such as `C:\Users\Lenovo\Desktop\二游名单.xlsx` can be passed with `--game-list`.
The workbook is treated as a watch matrix, not as an exhaustive `game x AI` polling queue.

Recommended command:

```powershell
python C:\Users\Lenovo\.codex\skills\game-community-ai-intelligence-daily-robust-preview\scripts\build_company_daily_pack.py `
  --output-dir D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs\company_daily_YYYYMMDD `
  --lookback-days 3 `
  --game-list C:\Users\Lenovo\Desktop\二游名单.xlsx
```

The prompt pack should:

- include `watch_games` and `watch_game_count` in `prompt_pack.json`;
- show a short watch-matrix summary in `prompt_pack.md`;
- tell Web AI tools to return only games with actual public information or community discussion from the last 3 days;
- avoid fabricating quiet games just to fill the matrix;
- include the category lenses:
  - 米哈游新增赛道观察：休闲种田/类动森、宠物养成
  - 库洛潜在方向观察：搜打撤/撤离射击类、动作竞技、硬核战斗向
  - 双方共同关注方向：3A 化、开放世界、高品质内容生产、跨端体验

Each hit item should carry concrete fields, not just a game name:

- `game_name`
- `matched_alias`
- `company` or `category`
- `event_type`
- `title`
- `plain_summary`: what happened, in plain language
- `specific_player_opinions`: what players are saying
- `why_watch`: why this is worth watching
- `business_use`: conservative business/customer conversation angle
- `url`: real URL when available; leave empty when unavailable
- `evidence_level`: `core_evidence`, `auxiliary_sample`, or `pending_lead`
- `risk_level`: `low`, `medium`, or `high`
- `limitations`

URL-less content must not be upgraded to core evidence. AI product pages, API pages, download pages, tool pages, and generic product introductions must be marked as prompt drift rather than treated as game-market evidence.

## Browser Collection

In Codex, use the in-app browser only after the operator has manually logged in to each Web AI page. Submit each prompt from `prompt_pack.md`, save the reply as JSON under `raw/<prompt_id>.json`, and keep the full visible reply in `response_text`.

For robust-preview v0.4.4 and later, use `scripts/in_app_browser_collectors_v044.mjs` as the repeatable Codex in-app-browser collector helper instead of ad-hoc Node snippets. This helper fixes the 2026-07-29 failures for 豆包 textarea confirmation, 千问 prompt-echo slicing, 文心 delayed textarea, Gemini editor focus, 点点 scoped send, and 知乎 clean route confirmation.

Raw output should follow this shape:

```json
{
  "prompt_id": "doubao_company_daily_001",
  "ai_tool": "豆包",
  "submitted_at": "",
  "retrieved_at": "2026-07-26",
  "response_text": "full reply text",
  "evidence": [
    {
      "company": "米哈游",
      "game_name": "原神",
      "matched_alias": "Genshin Impact",
      "product_tier": "daily_focus",
      "game_status": "已上线、持续运营",
      "scope": "game",
      "platform": "B站",
      "title": "public page title",
      "url": "https://...",
      "published_at": "2026-07-25",
      "event_type": "版本更新",
      "player_tendency": "分化",
      "player_intent": "抽卡 / 观望",
      "sentiment": "mixed",
      "risk_level": "medium",
      "summary": "evidence-backed summary",
      "specific_player_opinions": "concrete player opinions",
      "why_watch": "why it matters today",
      "access_status": "accessible",
      "limitations": "public searchable sample"
    }
  ],
  "pending_leads": [
    {
      "company": "米哈游",
      "game_name": "原神",
      "lead": "URL-less clue",
      "reason": "no_url"
    }
  ]
}
```

## Render HTML

```powershell
python C:\Users\Lenovo\.codex\skills\game-community-ai-intelligence-daily-robust-preview\scripts\render_company_daily_report.py `
  D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs\company_daily_test\raw `
  --output D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs\company_daily_test\reports\index.html `
  --lookback-days 3
```

## One-Command Preparation

```powershell
python C:\Users\Lenovo\.codex\skills\game-community-ai-intelligence-daily-robust-preview\scripts\run_company_daily_pipeline.py `
  --output-root D:\石声未来项目文件\游戏情报快讯\daily_ai_outputs
```

This creates the run folder, prompt pack, raw/report directories, an operator runbook, and an initial placeholder HTML. Re-run `render_company_daily_report.py` after AI raw outputs are saved.

## 5-10 Minute Daily Collection Mode

Use this mode when the user asks for a daily report and runtime/token cost matters.

Recommended queue:

1. Yuanbao: Chinese web, Tencent/news/WeChat ecosystem.
2. Doubao: Chinese web, Bilibili, Weibo, short-video clues.
3. Qianwen: Chinese-web supplemental search when already logged in or when extra coverage is needed.
4. Gemini or Grok: global web, Reddit/X/YouTube perspective.
5. Zhihu Direct Answer: Zhihu and controversy recap.
6. DianDian short fallback: Xiaohongshu/player tendency clues.

Rules:

- Claim already-open logged-in in-app browser tabs before opening anything new.
- Stop after one failed retry per AI tool.
- Use full AI-matrix + layer-2 deep-dive only for weekly/deep reports.
- If a tool returns raw prose instead of JSON, save it and continue. The renderer can still use parseable JSON and record limitations for the rest.
- If a tool, especially 千问, returns its own AI-product introduction instead of game/community results, mark the item as `prompt_drift`, do not add it to `evidence` or game-community `pending_leads`, and retry once with a shorter target-only query using actual company/game names.
- Do not use `game_name="二游大盘"` as a fallback for failed searches. Use it only when the evidence is truly a market-wide 二游 trend.
- Render with `scripts/render_company_daily_report.py --allow-no-url-evidence` when the user wants URL-less clues to appear with verification-search buttons.
- Prompt builders must put `COLLECT_RUN_ID` and `PROMPT_ID` on the first line. Browser collection must confirm the current `PROMPT_ID` appears in the newly submitted user message.
- Do not use generic browser send-button guessing. Use verified platform locators/adapters; if the send control is not verified after one retry, save a limitation and move on.
- 点点 / 小红书 and 知乎直答 can pass a short send test but still fail long-prompt collection if the automation stays in an old conversation or reads an old page body. For formal collection, start from a clean chat/search entry, clear old drafts, submit the prompt, and confirm the current `PROMPT_ID` appears in the newly submitted user message or the new result route before reading the reply.
- 点点 should use the verified Xiaohongshu AI Chat textarea and scoped visible submit control documented in `references/adapters/diandian_xiaohongshu.md`.
- 知乎直答 should start from `https://zhida.zhihu.com/`, fill the visible DraftEditor input, use the verified input-bar send control, and confirm the newly created `/search/...` result for the current `PROMPT_ID`; see `references/adapters/zhida_zhihu.md`.
- 文心一言 should use the Chinese-public-web safe prompt variant. Do not mention Grok, Gemini, X/Twitter, YouTube, VPN-like access wording, or overseas-access tooling in Wenxin prompts. If Wenxin returns a compliance refusal, save it as platform status, exclude it from evidence, and retry once with a shorter prompt focused on 百度/贴吧/新闻/中文公开网页.
- Grok should prefer a compact numbered `key: value` supplement when long JSON-style prompts are unstable. The accepted fields are `game_name`, `company/category`, `event_type`, `title`, `plain_summary`, `specific_player_opinions`, `why_watch`, `business_use`, `url`, `evidence_level`, `risk_level`, and `limitations`; `robust_structure_raw.py` can parse this short format.

## Robust Preview Collection

Use this path in `game-community-ai-intelligence-daily-robust-preview`.

1. Treat Web AI as raw collectors first. Do not require every reply to be perfect JSON.
2. Save every full reply under `raw/`, including Markdown, prose, partial JSON, prompt drift, and send-failure status records.
   v0.4.5 parser-rescue rule: if the raw text contains only prompt echo, placeholder JSON, old page body, or platform failure text, keep it in `platform_status` only. If it contains concrete Chinese numbered results but no real URL, extract them as `pending_leads`. If it contains `事件标题 / 发布日期 / 公开链接 / 核心内容`, extract real-URL rows as core evidence and preserve manual-review limitations.
   v0.4.7 collector-long-prompt-capture rule: before blaming the parser, inspect collector diagnostics. Doubao, Gemini, and Zhihu Direct Answer must capture the latest answer node or current-prompt answer tail, not whole `document.body.innerText`. Rank model answer nodes above user prompt nodes, reject off-topic answer drift, and retry the prompt pack's short fallback once for capture failures. DianDian must first prove that the tab is really in AI Chat input state; `/explore` with zero visible `aiSearchTextarea` is an entry failure, while multiple overlapping visible `aiSearchTextarea` nodes should be resolved by active-textarea selection rather than treated as an immediate failure.
3. For 千问, Grok, Gemini, and 点点, use the prompt pack's `fallback_prompt` once when:
   - user-message send confirmation fails;
   - prompt drift appears;
   - no parseable JSON block is found;
   - the reply is useful prose but cannot be parsed directly.
   For 文心一言, use the Wenxin-specific safe fallback instead of the generic global-Web fallback.
   For Grok, prefer a numbered short supplement over asking it to repair a large JSON object.
4. Run:

```powershell
python scripts/robust_structure_raw.py <raw_dir> --output <run_dir>\structured\robust_structured.json --report-date <YYYY-MM-DD> --lookback-days 3 --game-list C:\Users\Lenovo\Desktop\二游名单.xlsx
```

The structured JSON should preserve `plain_summary`, `why_watch`, `business_use`, `evidence_level`, and `limitations`.
It should also include coverage statistics:

- `watch_game_count`
- `hit_games`
- `hit_game_count`
- `unhit_game_count`
- `companies_hit_summary`
- `source_layer_summary`

5. Render:

```powershell
python scripts/render_company_daily_report.py <run_dir>\structured\robust_structured.json --output <run_dir>\reports\index.html --report-date <YYYY-MM-DD> --lookback-days 3 --allow-no-url-evidence
```

6. The default HTML report order is:
   1. 今日关键结论
   2. 游戏分类说明
   3. 重点产品/游戏命中
   4. 米哈游 / 库洛重点事件
   5. 按游戏证据表
   6. 玩家倾向变化 & 玩家建议
   7. 待验证线索
   8. 信源范围与限制

7. The top indicators must be explainable operational counts:
   - 本轮核心证据：有 URL 的证据数
   - 辅助样本：无 URL 但具体的 AI 观察数
   - 命中游戏：关注矩阵中本轮有信息的游戏数
   - 中高风险线索：medium/high 风险事件数

8. The default HTML must distinguish core evidence, auxiliary observations, and pending leads, but must not show platform collection/debug status. Keep platform status in normalized JSON for troubleshooting; render it only when `--show-platform-status` is explicitly used.
9. The final `信源范围与限制` module should state the 3-day time window, Web AI tools used, public source types covered, source layering, and limitations: this is not a full-web crawler, URL-less content is only a clue, and prompt drift is excluded from evidence.
10. Translate common English game/event titles into Chinese in the display layer while preserving raw AI replies, source files, and URLs unchanged.

