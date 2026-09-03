# AI Browser Execution

Use this reference when the user has logged in to Web AI tools in a browser and wants an agent to drive Web AI pages through Codex in-app browser, WorkBuddy external browser, or optional Playwright.

## Browser Rules

- Use existing logged-in sessions when tools can access them. In Codex in-app browser mode, if required AI pages are missing, open them for the operator and wait for manual login before submitting prompts.
- If the user explicitly asks for the Codex in-app browser / 内置浏览器, use in-app browser tabs instead of `.pw-ai-profile`.
- If the user explicitly asks for WorkBuddy, use WorkBuddy's external browser / agent-browser and read `references/workbuddy_external_browser_workflow.md`.
- Prefer a dedicated Playwright profile such as `.pw-ai-profile` only when the user explicitly wants standalone Playwright.
- Do not store, export, or ask for credentials, cookies, tokens, or browser profile contents.
- Do not bypass CAPTCHA, login walls, 403, paywalls, rate limits, or private groups.
- If an AI tool cannot access a platform, ask it for public-search-verifiable links and mark limitations.
- Save each AI response as raw JSON or Markdown before merging.

## AI Tool URLs

| AI site | URL | Primary role |
|---|---|---|
| Gemini | https://gemini.google.com/app | YouTube, Instagram, global web |
| Grok | https://grok.com/ | X/Twitter and real-time global social context |
| 豆包 | https://www.doubao.com/chat/?channel=browser_landing_page | 抖音, 微博, B站, 中文网页, TikTok support |
| 元宝 | https://yuanbao.tencent.com/chat/naQivTmsDa | 微信生态, 公众号, 新闻, 腾讯系内容 |
| 点点 | https://www.xiaohongshu.com/ai_chat | 小红书, 抖音, 种草内容, 社媒讨论；小红书任务先打开 https://www.xiaohongshu.com/ 再进入点点 |
| 知乎直答 | https://zhida.zhihu.com/ | 知乎, 问答讨论, 争议复盘 |
| 文心一言 | https://wenxin.baidu.com/ | 百度, 中文网页, 新闻, 贴吧, 百度知道/百科生态 |
| 千问 | https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5 | 中文网页, 新闻, 公开搜索, 社区线索；千问只是执行工具，不是检索对象 |

## In-App Browser Login Flow

Use this flow when the user says they want to log in through Codex's built-in browser:

1. Call `openTabs()` first and reuse already-open logged-in tabs whenever possible.
2. If required tabs are missing, tell the operator which AI pages are missing, then open the needed URLs in the in-app browser:
   - Yuanbao: `https://yuanbao.tencent.com/chat/naQivTmsDa`
   - Doubao: `https://www.doubao.com/chat/?channel=browser_landing_page`
   - Wenxin: `https://wenxin.baidu.com/`
   - DianDian / Xiaohongshu AI Chat: `https://www.xiaohongshu.com/ai_chat`
   - Zhihu Direct Answer: `https://zhida.zhihu.com/`
   - Qianwen: `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`
   - Gemini: `https://gemini.google.com/app`
   - Grok: `https://grok.com/`
3. Let the user complete login manually. Never request credentials, verification codes, cookies, local storage, tokens, or session files.
4. After the user says login is complete, call `openTabs()` and `claimTab()` for the visible logged-in pages.
5. Submit prompts only after confirming the page is the intended normal chat/search page.
6. Save raw outputs and mark Web AI results as secondary until URL-backed evidence is verified.

## WorkBuddy External Browser Flow

Use this flow when the user says WorkBuddy should run the polling:

1. Generate `prompt_pack.json` and `workbuddy_job.json`.
2. Ask the operator to manually log in to every required AI site in WorkBuddy's external browser.
3. WorkBuddy reads `workbuddy_job.json.queue` and opens the `entry_url` or reuses an already logged-in page for each `ai_tool`.
4. WorkBuddy must verify the normal chat/search page before submitting prompts. It must stop the item if it sees login, CAPTCHA, 403, product intro, repository, paywall, or a special-tool page.
5. WorkBuddy locates input and send controls through DOM, accessibility role/name, placeholder, contenteditable, visible text, or stable attributes. Fixed screen coordinates are forbidden.
6. WorkBuddy saves each raw reply to the queue item's `raw_output_path`.
7. WorkBuddy runs `scripts/render_game_polling_reports.py` or the `render_command` inside `workbuddy_job.json` to produce HTML.

## Required AI Response Contract

Ask AI tools to return strict JSON arrays. If they cannot return JSON, save their response as raw Markdown and manually convert only URL-backed evidence.

Each AI should:

- search within its strongest platforms
- return concrete post/news/video/question links
- summarize player tendency
- identify noteworthy events
- flag risk and limitations
- list URL-less leads separately

## 点点 / 小红书 Entry Rule

When the target platform is 小红书, do not use 点点 as a generic chat page only. The browser executor should open `https://www.xiaohongshu.com/` first, then enter 点点 from that page/context or navigate from the same tab to `https://www.xiaohongshu.com/ai_chat`.

点点 evidence rules:

- `xiaohongshu.com` and `xhslink.com` URLs are required for 小红书 evidence.
- Title-only notes, AI-only summaries, or search-like descriptions without URL must go to `pending_leads`.
- If 小红书 requires login, CAPTCHA, 403 handling, or blocks access, do not bypass it; record the limitation.

## 千问 / Qianwen Entry Rule

Use `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5` for ordinary text chat.

Observed normal-page signals from the 2026-07-27 in-app browser check:

- title includes `千问-阿里 AI 助手`
- page contains `Qwen` or `Qwen3.7-千问`
- page contains `向千问提问`
- page contains `新建对话`
- main input candidate is `[role="textbox"][contenteditable="true"]`

Avoid `API 服务`, `下载电脑端`, `PPT创作`, `AI生图`, `AI生视频`, `翻译`, `代码`, and other special-tool pages. If 千问 returns only prose without verifiable URLs, save the raw response and keep those claims in `pending_leads`.

Qianwen prompt-drift handling:

- Treat `千问`, `Qwen`, `通义千问`, and `阿里 AI 助手` as page identity / tool labels only, not search targets.
- If a reply only describes Qianwen/Tongyi product features, API service, downloads, model capability, or the AI assistant homepage, mark the run item as `prompt_drift`.
- Do not save AI-product-only replies as game-community `evidence` or `pending_leads`.
- Retry once with a shorter target-only query containing the actual company/game names, such as `米哈游 原神 星穹铁道 绝区零 最近3天 玩家反馈 舆情 链接`.
- Use `game_name="二游大盘"` only for true market-wide 二游 trends, never as a fallback for failed or drifted searches.

## Prompt Guardrail

Always include:

```text
没有 URL 或无法验证的内容请放入 pending_leads，不要放入 evidence。不要编造链接、标题、时间、玩家原话或数据。不要绕过登录、验证码、403、付费墙或私密群。
AI工具名只表示提交渠道，不是检索对象；不要把千问/Qwen/通义千问/阿里AI助手/豆包/元宝/文心一言/Gemini/Grok等工具官网当成游戏舆情来源。
```
