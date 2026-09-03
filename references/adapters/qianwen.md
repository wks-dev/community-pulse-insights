# Qianwen Adapter

Use this adapter when polling 千问 / Qianwen in Codex in-app browser, WorkBuddy external browser, or optional Playwright.

## Entry

- Preferred URL: `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`
- Entry mode: `direct`
- The operator must log in manually. Do not request credentials, verification codes, cookies, tokens, local storage, or browser profile files.

## Normal Page Signals

Observed in Codex in-app browser on 2026-07-27:

- title: `千问-阿里 AI 助手`
- visible text: `新建对话`
- visible text: `Qwen3.7-千问`
- visible text: `向千问提问`

These signals identify the execution page only. They are not search targets.

## Prompt Drift Guardrail

千问 is the AI tool used to submit the prompt, not the topic being researched.

Always include or preserve this rule in generated prompts:

```text
当前 AI 工具“千问”只表示本轮提交问题的平台，不是检索对象；不要检索或总结“千问”“Qwen”“通义千问”“阿里 AI 助手”官网、本页面、API 服务页或下载页。本轮唯一检索对象是游戏名、别名、厂商和玩家社区主题。
```

If the reply only returns Qianwen/Qwen/Tongyi product pages, API pages, downloads, feature introductions, or the AI assistant homepage:

1. Mark the item as `prompt_drift`.
2. Do not write the result into `evidence`.
3. Do not write it into `pending_leads` as a game-community clue.
4. Retry once with a shorter target-only prompt such as `米哈游 原神 星穹铁道 绝区零 最近3天 玩家反馈 舆情 链接` or `库洛 鸣潮 战双帕弥什 最近3天 玩家反馈 舆情 链接`.

## Exclusion Rules

Do not use these as the ordinary text chat target:

- `API 服务`
- `下载电脑端`
- `PPT创作`
- `AI生图`
- `AI生视频`
- `翻译`
- `代码`
- any other special-tool page

## Input Locator

Observed main input candidate:

```text
div[role="textbox"][contenteditable="true"]
```

Fallback candidates:

```text
[contenteditable="true"][role="textbox"]
[role="textbox"]
```

Before sending, always confirm there is a unique visible ordinary chat input, clear old content, insert the prompt, and confirm the prompt text is present in that input.

## Send And Reply

The send button was not L5-tested during the 2026-07-27 read-only check. During the first submit test:

1. Locate the send button by DOM/accessibility role/name or stable attributes.
2. Do not use fixed screen coordinates.
3. Do not infer success from the input clearing.
4. Confirm the new user message appears with the prompt marker.
5. Wait for the new AI reply after that user message.
6. Save the full visible reply under `raw/<prompt_id>.json`.

## Evidence Rule

Qianwen is a secondary Web AI search/summarization source. URL-backed records may enter `evidence`; URL-less prose must remain in `pending_leads`.

Do not use `game_name="二游大盘"` as a fallback for failed Qianwen searches. Use `game_name="二游大盘"` only when the returned content is truly a market-wide acg/二游 trend. Specific-game results must use the actual game name.

For browser automation, preserve the first prompt line containing `COLLECT_RUN_ID` and `PROMPT_ID`. Confirm that the same `PROMPT_ID` appears in the newly submitted user message before waiting for Qianwen's reply.

If Qianwen returns Qianwen/Qwen/Tongyi/Alibaba-AI product pages, API pages, downloads, feature introductions, or the AI assistant homepage, this is `prompt_drift`. Do not convert that failure into `game_name="二游大盘"`. `二游大盘` is valid only for real market-wide game-community trends, not AI-product-page drift.

## 2026-07-29 v0.4.4 Capture Fix

Observed failure: the page can contain the AI answer, then echo the current fallback prompt again near the bottom input. A collector that slices from the last `PROMPT_ID` will capture only the prompt echo and miss the answer.

Current rule:

1. Confirm the current prompt in the ordinary visible `div[role="textbox"][contenteditable="true"]`.
2. Submit with Enter.
3. After the answer appears, save the full visible page text or a scoped full answer container.
4. Do not slice from the last prompt marker.
5. Let `robust_structure_raw.py` remove prompt echoes and JSON/debug fragments before rendering.
