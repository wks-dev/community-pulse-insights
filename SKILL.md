---
name: game-community-ai-intelligence-daily-robust-preview
description: Robust preview fork of the daily game community AI intelligence workflow for 5-10 minute miHoYo/Kuro/acg market sentiment monitoring with Codex in-app browser Web AI polling, resilient raw output capture, prompt-drift fallback, relaxed parsing for Qianwen/Grok/Gemini/DianDian, evidence normalization, and polished HTML dashboard reports. Use when users want to test improved collection reliability without modifying the stable daily skill.
---

> Robust preview version: this is an isolated fork for testing reliability improvements. Do not modify the stable `game-community-ai-intelligence-daily` skill from this copy.

# Game Community AI Intelligence

## When To Use

Use this skill when the user wants game-community public-opinion intelligence from natural language, a game/category target, an Excel/CSV game list, or a scheduled daily monitoring need.

The user does not need to upload raw posts. They must provide an analysis target: a game name, platform, time range, topic, genre/category, competitor set, market segment, Web AI tool set, or a game-list file.

## Supported Modes

- **Single game**: analyze one game on one or more platforms.
- **Category scan**: analyze a category such as 二游, 女性向, SLG, open-world mobile games.
- **All-platform trend**: expand to public platforms and report platform differences and propagation.
- **Game-list polling**: read a workbook/CSV of games and aliases, generate one prompt per game per AI tool, save a prompt pack, then produce one HTML per game plus a combined HTML report after AI outputs are collected.
- **Daily 9 AM monitoring**: use game-list polling with a 24-hour lookback window and a scheduled run.
- **Codex in-app browser execution**: default execution surface inside Codex when the operator has already manually opened and logged in to the Web AI pages. Use the Browser skill to claim visible tabs, submit prompts, wait for replies, extract raw outputs, and save them under `raw/`.
- **WorkBuddy external browser execution**: default execution surface for WorkBuddy. Generate `workbuddy_job.json`, let the operator manually log in to AI pages in WorkBuddy's external browser, then have WorkBuddy submit prompts, save raw replies, and render HTML.
- **Optional Playwright execution**: use `scripts/run_web_ai_with_playwright.js` only for standalone Chrome or non-Codex/non-WorkBuddy runners when the user explicitly wants Playwright.

## Default Workflow

1. Parse the user request with `scripts/parse_task.py`.
2. Build search queries with `scripts/build_query_pack.py` when public search is needed.
3. Build Web AI prompts with `scripts/build_web_ai_prompts.py`, list prompts with `scripts/build_game_polling_pack.py`, or run prompt/report generation with `scripts/run_game_polling_pipeline.py`.
4. Submit prompts through the requested browser/automation surface. In Codex, prefer already logged-in in-app browser tabs and read `references/in_app_browser_polling_workflow.md`. If required Codex in-app browser pages are missing, open them for the operator, wait for manual login, then continue. In WorkBuddy, use external browser / agent-browser execution and read `references/workbuddy_external_browser_workflow.md`.
5. Save raw AI outputs before merging.
6. Normalize URL-backed evidence and pending leads.
7. Render Markdown/HTML with `scripts/render_report.py`, `scripts/render_daily_game_report.py`, or `scripts/render_game_polling_reports.py`.

## Robust Preview Workflow

Use this isolated preview path when collection reliability matters more than perfect first-pass formatting.

1. Build the company prompt pack with `scripts/build_company_daily_pack.py`. For richer reports, use `--report-mode weekly` with a 7-day window. When the user provides a workbook such as `C:\Users\Lenovo\Desktop\二游名单.xlsx`, pass it with `--game-list` as a watch matrix. This matrix narrows the scope and prompt vocabulary; it is not a 40-game exhaustive polling queue.
2. Submit the normal prompts first and save every full AI reply under `raw/`, even when the reply is Markdown, prose, partial JSON, or an error record.
3. In Codex, use `scripts/in_app_browser_collectors_v044.mjs` as the formal in-app-browser collector helper when submitting prompts from the Node REPL. In v0.4.7 this helper performs long-prompt targeted reply capture for Doubao, Gemini, Zhihu Direct Answer, and DianDian instead of saving whole-page text or prompt echoes. Do not hand-roll platform submission logic unless the helper is missing or the user explicitly asks for a diagnostic run.
4. For Qianwen, Grok, Gemini, DianDian, Zhihu Direct Answer, and Wenxin, use the prompt pack's `fallback_prompt` once when send confirmation fails, prompt drift appears, or the reply is useful but not strict JSON.
5. Run `scripts/robust_structure_raw.py <raw_dir> --output <run_dir>/structured/robust_structured.json`; include `--game-list` when the prompt pack used a watch matrix.
6. Preserve and display the robust fields `plain_summary`, `specific_player_opinions`, `why_watch`, `business_use`, `evidence_level`, and `limitations`. URL-less content must remain `auxiliary_sample` or `pending_lead`; it must not become core evidence.
7. Render `structured/robust_structured.json` with `scripts/render_company_daily_report.py --allow-no-url-evidence`.
8. Keep report classes separate:
   - URL-backed public pages: core evidence.
   - URL-less but concrete AI observations: auxiliary samples or pending leads.
   - Unverified clues: pending leads with verification buttons.
   - Send failures, prompt drift, parse failures: save as `platform_status` in normalized JSON; do not show them in the default executive HTML dashboard unless `--show-platform-status` is explicitly used.
9. Use the executive report order: 本周/今日关键结论 -> 关注矩阵覆盖 -> 赛道新闻与案例 -> 重点产品/游戏命中 -> 米哈游 / 库洛重点事件 -> 其他二游与竞品动态 -> 按游戏证据表 -> 玩家倾向变化 & 玩家建议 -> 待验证线索 -> 信源范围与限制. Do not show static category definitions when the user expects news content.
10. In weekly mode, keep the default `layer2_weekly_expansion` prompts enabled for 豆包, Gemini, and Grok to improve watch-matrix hits, other 二游 coverage, and sector-case richness.
11. For 豆包, confirm the prompt in the textarea `value`, not only in `body.innerText`; the textarea value is the send proof before pressing Enter.
12. For 千问, save the full visible answer after current `PROMPT_ID` confirmation; do not slice from the last marker because the page can echo the prompt after the answer.
13. For 点点 / 小红书, the page may expose multiple overlapping `textarea[name="aiSearchTextarea"]` nodes. Select the active textarea by visibility, `tabIndex=0`, non-hidden state, and `.ai-chat-welcome__input` / `.textarea-container.ai-chat-input-box` ancestry; clear and verify the current `PROMPT_ID`, then click only the scoped `.ai-chat-welcome__input .submit-button-wrapper` or `.textarea-container.ai-chat-input-box .submit-button-wrapper`. Do not use a generic button, coordinate, or Enter fallback. Confirm the new user message and finished AI reply before saving evidence. If the long prompt fails once, retry the short fallback through the same strict sequence; otherwise save `send_unconfirmed` in `platform_status`. Use `references/adapters/diandian_xiaohongshu.md`.
14. For 知乎直答, always return to `https://zhida.zhihu.com/`, paste into the unique visible DraftEditor, require the editor text to contain current `PROMPT_ID`, then confirm a new `/search/...` route before saving.
15. For 文心一言, navigate to `https://wenxin.baidu.com/`, wait up to 45 seconds for exactly one visible `textarea#chat-textarea.ci-textarea`, and use exactly one visible enabled `#ci-submit-button-ai.ci-submit-button-ai-active`; never fall back to an arbitrary `textarea` or nearest send button. Confirm the new user message contains the current `PROMPT_ID` and a new answer node appears. If a compliance refusal appears, save it as platform status and retry once with a shorter 百度/贴吧/新闻/中文公开网页 prompt. Use `references/adapters/wenxin.md`.
16. For Gemini, prefer the unique visible Quill editor and keyboard paste. If clicking the editor times out due to browser event translation, record `adapter_error` and retry once with the short fallback; do not click microphone or other adjacent controls.
17. For Grok, use a numbered short supplement when large JSON prompts are unreliable. Save the raw reply and let `robust_structure_raw.py` parse the `key: value` blocks; only confirmed current-prompt replies can enter evidence.
18. Keep the daily runtime within 5-10 minutes by using at most one retry per brittle platform. Weekly expanded reports may take longer; still do not bypass login, CAPTCHA, 403, or access limits.
19. For collector debugging, use `scripts/in_app_browser_diagnostics_v046.mjs` and its `runPlatformDiagnostics({ iab, outputRoot })` helper. It sends short marker prompts, records visible inputs/buttons/routes/reply-marker checks, and writes diagnostics under `daily_ai_outputs/platform_diagnostics_v046_*`. Do not mix these diagnostic files into formal report raw data.

## Game-List Polling Workflow

Use this workflow when the user provides a workbook such as `二游名单.xlsx` and wants every game polled across multiple AI tools.

1. Read `references/game_list_polling_workflow.md`.
2. Generate a reusable blank template from `references/universal_game_polling_prompt.md` when the user asks for a generic prompt without a game name.
3. Normalize the workbook with `scripts/load_game_list.py`. Keep all aliases.
4. Build the prompt pack with `scripts/build_game_polling_pack.py`. Default tools are 元宝, 豆包, 文心一言, 千问, 点点, 知乎直答, Gemini, and Grok. Default mode is one prompt per game per AI tool.
5. In Codex, use `references/in_app_browser_polling_workflow.md` to submit the saved prompt pack through the built-in browser. The operator must manually log in to each AI page first; the skill must not request, store, export, or infer credentials.
6. In WorkBuddy, use `references/workbuddy_external_browser_workflow.md` and `workbuddy_job.json`. The operator manually logs in through WorkBuddy's external browser; WorkBuddy submits prompts, saves raw replies, and renders HTML.
7. Outside both Codex and WorkBuddy, use `scripts/run_web_ai_with_playwright.js` only if the target browser profile is already logged in and the user explicitly accepts standalone Playwright/Chrome execution.
8. Normalize AI outputs into URL-backed evidence and pending leads. Do not upgrade URL-less AI summaries.
9. Render reports with `scripts/render_game_polling_reports.py`. Produce:
   - `index.html`: combined cross-game report.
   - `games/<game_id>_<slug>.html`: one HTML report per game.

For one-command prompt/report generation, run `scripts/run_game_polling_pipeline.py <game_list>`. It also writes WorkBuddy handoff files by default: `workbuddy_job.json`, `workbuddy_queue.csv`, and `workbuddy_runbook.md`. Its `--submit` mode uses the optional Playwright runner, not the Codex in-app browser or WorkBuddy agent-browser.

## Daily 9 AM Monitoring Workflow

For a request like "每天 9 点给出名单上所有游戏的舆情日报":

1. Read the game list with `scripts/load_game_list.py`. Accept `.xlsx`, `.xls`, `.csv`, and `.tsv`.
2. Prefer `scripts/run_game_polling_pipeline.py` for repeatable prompt/report generation or `scripts/build_game_polling_pack.py` for prompt generation only.
3. In Codex, inspect the in-app browser tabs first. If required AI pages are not open, open them in the in-app browser, tell the operator which sites need manual login, wait until the operator confirms login is complete, then claim those logged-in tabs and submit prompts using `references/in_app_browser_polling_workflow.md`.
4. In WorkBuddy, ask the operator to manually log in to the required AI pages in WorkBuddy's external browser, then execute `workbuddy_job.json` using `references/workbuddy_external_browser_workflow.md`.
5. Use standalone Playwright only outside Codex/WorkBuddy or when explicitly requested.
6. Render the daily HTML report with `scripts/render_game_polling_reports.py`.
7. If a Codex or WorkBuddy automation is created, schedule it for 09:00 local time in the project where outputs should be saved.

## Evidence Rules

- Core conclusions must cite URLs from original posts, comments, official pages, or search-verifiable pages.
- Web AI responses may guide discovery and provide secondary summaries, but they cannot become core evidence without URLs.
- Content without a URL, inaccessible material, or AI-only summaries must remain in "辅助观察" or "待验证线索".
- If a platform limits direct access, use only public search indexes and accessible links, and label the sample as "公开可检索样本，不代表全量社区舆情".
- Every final report must state sample coverage, retrieval date, confidence, and evidence limitations.

## Access Rules

- Use existing logged-in browser sessions when available and explicitly intended by the user. If a required Codex in-app browser page is missing, open the page for the operator and wait for manual login before continuing.
- The operator is responsible for logging in to each AI site manually in the browser. The skill only operates after login is complete.
- If the user specifies the Codex in-app browser, do not switch to `.pw-ai-profile` or standalone Chrome unless they approve it.
- If the user specifies WorkBuddy, use WorkBuddy's external browser / agent-browser workflow and `workbuddy_job.json`; do not assume Codex in-app browser APIs exist.
- Do not ask for, store, export, or print credentials, cookies, tokens, or browser profile contents.
- Do not bypass login, CAPTCHA, 403, paywalls, rate limits, private groups, or other access controls.
- If an AI tool cannot return concrete URLs, place its result in `pending_leads` or secondary observations.

## Missing In-App Browser Pages

Use this flow whenever the user asks Codex to run Web AI polling but one or more required AI pages are not already open in the in-app browser.

1. Call `openTabs()` through the Browser skill and compare current tabs against the selected AI tool set.
2. If tabs are missing, briefly tell the user which pages are missing, then open the needed URLs in the Codex in-app browser:
   - Yuanbao: `https://yuanbao.tencent.com/chat/naQivTmsDa`
   - Doubao: `https://www.doubao.com/chat/?channel=browser_landing_page`
   - Wenxin: `https://wenxin.baidu.com/`
   - DianDian / Xiaohongshu AI Chat: `https://www.xiaohongshu.com/ai_chat`
   - Zhihu Direct Answer: `https://zhida.zhihu.com/`
   - Qianwen: `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`
   - Gemini: `https://gemini.google.com/app`
   - Grok: `https://grok.com/`
3. Stop automation and ask the operator to finish login manually in those pages. Do not request credentials, verification codes, cookies, local storage, tokens, or browser profile files.
4. After the operator says login is complete, call `openTabs()` again, claim the tabs, and verify each page is a normal chat/search page rather than a login page, CAPTCHA, 403, paywall, product intro page, knowledge-base-only page, or special-tool page.
5. For fast 5-10 minute daily reports, open only the high-yield set first: Yuanbao, Doubao, Zhihu Direct Answer, DianDian, Qianwen when the page is already logged in or extra Chinese-web coverage is needed, and either Gemini or Grok. Add Wenxin when Baidu/Tieba coverage is required. Open the full AI matrix only for deep/weekly runs or explicit full-matrix requests.
6. If a page still requires login or fails identity checks after the operator confirms, record the limitation and continue with the remaining available tools.

## Web AI Tool Roles

- **Gemini**: global web, YouTube, Instagram-oriented discovery. url: `https://gemini.google.com/app`
- **Grok**: X/Twitter and real-time global social context. url: `https://grok.com/`
- **豆包**: Chinese web, 抖音, 微博, B站, and TikTok support. url:'https://www.doubao.com'
- **元宝**: 微信生态, 公众号, 新闻, 腾讯系内容. url:'https://yuanbao.tencent.com'
- **点点**: 小红书, 抖音, 种草内容, lifestyle/community discussion. For 小红书-specific work, open 小红书 first and enter 点点 from that context or use `https://www.xiaohongshu.com/ai_chat`; URL-less 点点 observations remain pending leads.
- **知乎直答**: 知乎, Q&A discussion, controversy recap. url:'https://zhida.zhihu.com'
- **文心一言**: 百度, 中文网页, 新闻, 贴吧, 百度知道/百科 ecosystem. url:'https://wenxin.baidu.com'
- **千问**: Chinese web, news, public search, and cross-platform community clues. url: `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`; 千问/Qwen/通义千问 are execution-page identity labels, not research targets. Avoid AI-product pages, API Service, downloads, PPT creation, image/video generation, translation, code, and other special-tool pages.

Use OpenAI-compatible APIs for structured tagging, sentiment classification, topic classification, risk rating, and report synthesis. Support `EXTERNAL_AI_API_KEY`, `EXTERNAL_AI_BASE_URL`, and `EXTERNAL_AI_MODEL`.

## Required Daily HTML Report Modules

Always include:

1. 日报总览
2. 样本范围与限制
3. 值得关注的事件
4. 按游戏分组舆情
5. 玩家倾向与情绪
6. 平台差异
7. 风险预警
8. 今日新增/升温/降温
9. 证据链接表
10. 待验证线索

## Fast Company Daily Mode

Use this mode first when the user asks for a daily report about 米哈游, 库洛, 战双帕弥什, the supplied 米哈游 product matrix, or 二游大盘.

- Default lookback window: recent 3 days.
- Keep this mode separate from previous single-game tests and exhaustive game-list polling. Use run IDs like `company_daily_YYYYMMDD`, and do not read old `codex_1game_*` or `game_polling_*` raw outputs unless the user explicitly asks to compare with historical samples.
- First layer: company/market fast scan. Build one detailed prompt for each selected Web AI tool with `scripts/build_company_daily_pack.py` or prepare a run folder with `scripts/run_company_daily_pipeline.py`.
- Second layer: community deep dive. By default, also generate 点点 and 知乎直答 prompts to capture 小红书/知乎 community discussion, player tendency, controversy, suggestions, and platform-specific sentiment.
- Read `references/company_focus_matrix.md` before changing product scope.
- Read `references/fast_daily_intelligence_workflow.md` before running the daily workflow.
- Render the polished HTML daily report with `scripts/render_company_daily_report.py`.
- Use exhaustive `game x AI` polling only for deep audit, weekly baseline, or explicit full-list requests.

## 2026-07-27 Fast-Run Lessons

Use these rules for current daily runs so the workflow stays inside a practical 5-10 minute operator window.

- Treat the default daily report as a fast collection, not a full AI-matrix audit.
- Claim already-open logged-in in-app browser tabs first. Do not open duplicate AI pages when usable tabs already exist.
- For a 5-10 minute daily run, prefer this high-yield queue: Yuanbao, Doubao, Qianwen when already logged in, Gemini or Grok, Zhihu Direct Answer, and DianDian short fallback. Add Wenxin only when Baidu/Tieba coverage matters more than runtime.
- Use the full AI-matrix plus 2 deep-dive prompt pack only for weekly/deep runs or when the user explicitly accepts a longer runtime.
- Do not spend more than one retry on a platform whose user message cannot be confirmed.
- If DianDian/Xiaohongshu long community prompt is typed but not sent, immediately switch to a short Xiaohongshu-focused fallback prompt and mark `short_fallback=true`.
- If Grok or Wenxin returns useful prose but not strict JSON, save the raw reply and continue. Do not wait for perfect formatting.
- If a Web AI send cannot be confirmed against the current `PROMPT_ID`, save platform status only. Do not parse old page text or unconfirmed drafts into evidence.
- Wenxin compliance refusals that mention network-security or access-tool policy are prompt drift for this workflow; exclude them from evidence and retry once with the Wenxin-safe prompt.
- Grok short supplements may use numbered `key: value` items. Keep URLs only when they are real links; URL-less Grok items remain auxiliary samples or pending leads.
- If Qianwen or another AI returns its own product introduction instead of game/community results, mark `prompt_drift=true`, do not add it to `evidence` or game-community `pending_leads`, and retry once with only actual company/game/community keywords.
- Do not use `game_name="二游大盘"` as a fallback for failed searches. Use it only when the item is truly a market-wide 二游 trend; specific-game items must use actual names such as 原神, 崩坏：星穹铁道, 绝区零, 鸣潮, or 战双帕弥什.
- Treat placeholder strings such as `https://...`, `如有真实链接则填写`, or `没有就留空` as no URL. They must not become evidence links.
- Render current daily reports with the XHS preview renderer when the user wants clickable verification buttons for URL-less clues.
- Hide platform collection status from final HTML dashboards by default. Keep status records in `normalized_company_evidence.json` for troubleshooting, and show them only with `--show-platform-status`.
- Translate common English game/event titles into Chinese for display. Preserve raw AI replies, source files, and URLs unchanged.
- In company focus cards, group events into `社区讨论`, `版本更新`, and `新闻公告`. In the insights section, show `玩家倾向变化` plus `玩家建议`; do not label the section as reusable design points.
- Read `references/codex_inapp_browser_troubleshooting.md` before retrying if send confirmation, JSON parsing, DianDian submission, or local `file://` report opening fails.
- Generated prompts must place `COLLECT_RUN_ID` and `PROMPT_ID` on the first line. The browser executor must confirm the current `PROMPT_ID` in the newly submitted user message before waiting for a reply.
- Do not use generic send-button guessing. Use verified platform adapters/locators only; if the send control cannot be verified, save a limitation and continue.

## Robust Fallback Rules

- Treat Web AI replies as raw collection first, not as guaranteed standard JSON.
- v0.4.9-stage1 raw audit rule: after raw capture and before report judgment, run `scripts/audit_raw_quality.py` directly or let `scripts/robust_structure_raw.py` invoke it automatically. The audit writes `structured/raw_quality_audit.json` and `structured/raw_quality_audit.csv`, and `robust_structured.json` must include `raw_quality_audit`, `valid_answer_count`, `invalid_answer_count`, and `valid_answer_by_ai`.
- v0.4.9-stage1 valid-answer rule: `status=ok` only means a raw file was saved. It is not a successful platform contribution unless `valid_answer=true` and the raw text is a current confirmed answer, non-empty, not prompt echo, not page shell, not refusal, and contains concrete game/event/player-feedback/URL or `no_url` clue signals.
- v0.4.9-stage1 invalid-answer rule: prompt echoes, page shells, history-mixed captures, compliance refusals, incomplete fragments, and unconfirmed sends must explain their `invalid_reason` in the raw audit. These rows can stay in `platform_status` for troubleshooting but must not inflate effective-platform counts.
- v0.4.9-stage2 answer-rescue rule: `scripts/in_app_browser_collectors_v044.mjs` must record a pre-send page snapshot, confirm the current `PROMPT_ID` after send, and enter answer rescue when platform selectors miss or return text that fails the capture quality gate. Rescue ranks only new current-prompt tail text and answer-like nodes by game names, player-feedback terms, URL/`no_url`, numbered/table/key-value structure, and reasonable length; it penalizes prompt markers, JSON schema examples, history, page chrome, tool panels, input placeholders, and AI product introductions.
- v0.4.9-stage2 rescue-candidate rule: a rescued answer is saved only as `capture_mode=rescue_candidate`, `answer_confirmed=false`, `valid_answer=null`, `needs_human_review=true`, with `candidate_score` and `candidate_reason`. It must not auto-count as an effective AI platform and must pass the stage1 raw audit before any content can enter `evidence`, `pending_leads`, or `auxiliary_sample`.
- v0.4.9-stage2 dirty-page rule: if a page contains only input placeholders, old history, navigation, download/tool panels, or product-introduction text, save `capture_failed` / `answer_not_captured` instead of inventing a rescue candidate.
- v0.4.9 grouped-short-scan rule: `scripts/build_company_daily_pack.py` defaults to `--collection-strategy grouped_short_scan`. It splits the watch matrix into `group_core_mihoyo_kuro`, `group_cn_competitor_ops`, `group_new_product_watch`, and `group_sector_female_lifestyle`, then sends short group prompts instead of giving every AI tool the full 44-game long weekly schema. Use `--collection-strategy legacy_long_scan` only for explicit comparison or rollback testing.
- v0.4.9 brittle-platform prompt rule: Doubao, DianDian, Zhihu Direct Answer, Qianwen, Wenxin, and Yuanbao use short grouped prompts by default; Grok uses short numbered supplements; Gemini uses medium grouped prompts. Each short prompt asks for 5-8 concrete items with game name, event/title, platform, player feedback, URL or `no_url`, and why it matters.
- v0.4.9 contribution-count rule: `contributing_ai_count` and `contributing_ai` are valid only when an AI platform has `valid_answer=true` in `raw_quality_audit` and actually contributes report-visible `evidence`, `pending_leads`, or `auxiliary_sample`. `status=ok`, prompt echoes, page shells, refusals, and invalid rescue candidates must not inflate effective-platform counts.
- v0.4.9 report-audit-summary rule: the HTML report top area should show only compact raw audit counts: effective contributing AI platforms, true-answer raw count, prompt echo count, page shell count, refusal count, and rescue-candidate count. Detailed audit rows remain in `structured/raw_quality_audit.json` and `.csv` unless a debug/status view is explicitly requested.
- v0.4.9-hotfix1 report-accuracy rule: when `--game-list` is missing or stale, `scripts/robust_structure_raw.py` must recover the watch matrix from the current run's `prompt_pack.json`. If numbered key/value rows were parsed from a raw answer, do not also run heuristic URL-context slicing on that same answer; reject cross-field shards such as `tations:`, `nce_level:`, or multi-field prompt/report fragments before they can enter report-visible evidence.
- v0.4.9-hotfix1 Grok/Yuanbao rescue rule: answer rescue must enumerate all structured `game_name`/`游戏名` answer segments after the current `PROMPT_ID`, not only the last body tail. A prompt that remains in the input box is not send confirmation; require a new user-message hash or a new AI reply node before treating the page as current-prompt captured.
- v0.4.9-hotfix2 display-cleanup rule: default HTML is a business-facing report, not a collection dashboard. Do not show raw-audit cards, true-answer/raw counts, prompt echo/page-shell/refusal/rescue-candidate counts, `数据已实时更新`, metric notes, or process conclusions such as watch-matrix count, hit-game count, URL-lead count, auxiliary-sample count, medium/high count, or URL verification caveats in the main HTML. Keep those details in structured JSON, raw audit files, issue summaries, and version records.
- v0.4.9-hotfix2 sector-case rule: `赛道新闻与案例` must be filled from concrete sector signals when available. Valid sector signals include 新品测试/预约/PV/首测, 宠物养成, 搜打撤, 动作竞技, 开放世界/3A 化, 休闲种田, and gameplay/content-form lifestyle cases. `女性向` alone is not a sector trigger and must not route content into this module by itself.
- v0.4.8 raw-first collector rule: for confirmed current-prompt AI replies, the collector saves raw first even when the answer is weak, non-JSON, prose, Markdown, short, or possibly drifted. Mark saved raw as `status=ok`, `capture_quality=weak|normal|strong`, and `needs_structure_review=true`; keep the more specific adapter note in `capture_quality_detail` or `error`. Only unconfirmed sends, missing input controls, route failures, login/access blocks, and empty replies remain collection errors.
- v0.4.8 structure-gate rule: `robust_structure_raw.py` decides whether saved raw becomes evidence. Real URL rows may become core evidence; URL-less but concrete rows become auxiliary samples or pending leads; prompt echoes, tool introductions, old page text, product pages, placeholder templates, and HTML/page-shell text stay in `platform_status` and must not pollute report-visible evidence.
- v0.4.8 Zhihu Direct Answer node rule: after a fresh `/search/...` route, prefer `[data-testid="Block:zhida_answer_result_block"]` and `.Render-markdown` answer nodes. Reject `[data-testid="Block:zhida_input_box"]`, `InputLike`, `Editable-content`, and placeholder text such as `输入你的问题，或使用...`; those are page chrome, not AI answers.
- v0.4.8 URL sanity rule: truncated or placeholder URLs, including `https://...` and known clipped domains such as `https://www.zhihu.co`, must be treated as missing URLs. They can support pending leads only, not core evidence.
- v0.4.6 DianDian rule: if `https://www.xiaohongshu.com/ai_chat` lands on `/explore` or lacks exactly one visible `textarea[name="aiSearchTextarea"]`, record `diandian_ai_chat_entry_not_reached` with safe DOM diagnostics. Do not guess generic buttons or coordinates.
- v0.4.7 long-prompt rule: Doubao and Gemini may successfully generate full answers after the first completion wait but still be misread if the collector picks the user prompt node. Score candidate answer nodes by structured evidence fields, game-industry terms, real URLs, and model-response selectors; exclude `You said`, `Conversation with Gemini`, prompt instructions, and current `PROMPT_ID` echoes.
- v0.4.7 Zhihu Direct Answer rule: a fresh `/search/...` route is still not enough when the returned answer is old context such as a webpage-briefing task. If the answer lacks game-intelligence signals or contains off-topic markers, save `answer_drift` and retry the prompt pack's short fallback once.
- v0.4.7 DianDian rule: `/ai_chat` can show two visible overlapping AI Chat textareas. This is a valid page state, not an immediate failure. Use the active textarea selection rule documented in `references/adapters/diandian_xiaohongshu.md`.
- v0.4.5 parser rescue rule: after raw collection, always distinguish browser/page failure from parser failure. If a platform has a confirmed current-prompt raw reply but the first JSON parse only finds prompt templates or placeholder URLs, let `robust_structure_raw.py` continue with Chinese numbered-block parsing and URL-context extraction. Do not stop merely because a placeholder JSON block was found.
- Chinese numbered replies such as Qianwen fallback output can enter `pending_leads` when they contain concrete game, title, player feedback, and risk fields but no real URL. Citation markers such as `[1]` are not URLs and must not become core evidence.
- Public-link prose such as Wenxin event blocks should be extracted by `事件标题 / 发布日期 / 公开链接 / 核心内容`; rows with real URLs can enter core evidence, while the report must still ask for manual link review in `limitations`.
- Platform errors, prompt drift, old visible pages, prompt echoes, and page-shell text must stay in `platform_status`. They must not be appended to report-visible `pending_leads` by default.
- Do not wait for perfect JSON from Grok, Qianwen, Wenxin, or Gemini. Save raw text and let `robust_structure_raw.py` extract valid JSON blocks or URL-bearing prose.
- Use Qianwen fallback when the reply mentions Qianwen/Qwen/Tongyi/Alibaba AI product pages, API service, downloads, PPT, image/video generation, translation, code, or returns `game_name="二游大盘"` for a tool-page failure.
- Use DianDian fallback when the long Xiaohongshu/community prompt is typed but the user message cannot be confirmed.
- Use Gemini fallback once with a short prompt; if the user message is still not confirmed, record platform status and continue.
- Use Grok fallback when the reply is long prose/Markdown and no parseable JSON block is found.
- Use Wenxin safe fallback when the reply refuses due to access-tool or network-policy wording; remove global-Web tool names and ask only for Chinese public pages.
- Never parse responses from unconfirmed sends into evidence, even if visible page text contains game-related material.
- Never upgrade URL-less AI prose into core evidence. It may be displayed only as auxiliary sample or pending lead.
