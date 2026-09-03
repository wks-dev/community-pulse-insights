# In-App Browser Polling Workflow

Use this reference when the user wants Codex to use the built-in browser with Web AI pages that the operator has manually logged in to.

## Scope

This workflow is for Codex only. It is not a standalone command-line script because the Codex in-app browser API is provided by the runtime, not by Python or Node.

Use it when:

- The user has opened and logged in to 元宝、豆包、文心一言、千问、点点、知乎直答、Gemini、Grok in the Codex in-app browser.
- The task is to submit a saved `prompt_pack.json` or selected prompt queue to those tabs.
- Raw AI outputs must be saved before any evidence merge.

The operator must complete login manually. Codex must not ask for passwords, one-time codes, cookies, tokens, browser storage, or profile files, and must not try to bypass login, CAPTCHA, 403, or other access controls.

Use `scripts/run_web_ai_with_playwright.js` only when the user explicitly wants standalone Playwright/Chrome or when the target platform cannot access the Codex in-app browser.

When a run involves first-time validation, stale browser tabs, rich-text inputs, page identity confusion, 点点 / 小红书 failures, 知乎直答 route issues, 文心一言 non-JSON output, or local HTML display problems, read `references/codex_inapp_browser_troubleshooting.md` before retrying.
For platform-specific send and confirmation failures, also read `references/platform_failure_matrix.md`.

For robust-preview v0.4.4 and later, import the formal in-app-browser collector helper from:

```js
await import("C:/Users/Lenovo/.codex/skills/game-community-ai-intelligence-daily-robust-preview/scripts/in_app_browser_collectors_v044.mjs")
```

Use this helper instead of ad-hoc submission snippets when possible. It contains the current fixes for 豆包 textarea-value confirmation, 千问 full-page answer capture, 文心 delayed textarea wait, Gemini keyboard-paste editor confirmation, 点点 strict scoped textarea/send checks, and 知乎 clean-home/new-search-route confirmation.

## Missing Tabs And Manual Login Preparation

Use this preparation flow before submitting any prompt when the required AI pages are not already open.

1. Call `openTabs()` and list the current in-app browser tabs by URL/title.
2. Compare the visible tabs with the selected AI tool set:
   - Yuanbao: `https://yuanbao.tencent.com/chat/naQivTmsDa`
   - Doubao: `https://www.doubao.com/chat/?channel=browser_landing_page`
   - Wenxin: `https://wenxin.baidu.com/`
   - DianDian / Xiaohongshu AI Chat: `https://www.xiaohongshu.com/ai_chat`
   - Zhihu Direct Answer: `https://zhida.zhihu.com/`
   - Qianwen: `https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5`
   - Gemini: `https://gemini.google.com/app`
   - Grok: `https://grok.com/`
3. If pages are missing, tell the operator which AI pages will be opened, then open those URLs in the Codex in-app browser.
4. Stop submission work and ask the operator to log in manually in the newly opened pages. The operator should reply when all required pages are ready.
5. Do not request, reveal, store, export, or inspect credentials, verification codes, cookies, local storage, tokens, or browser profile files.
6. After the operator confirms login, call `openTabs()` again, claim the intended tabs, and verify each page identity:
   - normal chat/search page is visible;
   - input area can be uniquely identified;
   - not a login page, CAPTCHA, 403, paywall, product intro page, repository/knowledge-base-only page, special-tool page, or blocked page.
7. If a page still fails identity checks, save a raw error wrapper for that AI tool and continue with available tools.
8. For 5-10 minute daily mode, open the high-yield set first: Yuanbao, Doubao, Qianwen when already logged in or extra Chinese-web coverage is needed, Zhihu Direct Answer, DianDian, and either Gemini or Grok. Add Wenxin for Baidu/Tieba coverage or run the full AI matrix only when the user asks for full/deep coverage.

## Required Steps

1. Load the Browser skill and use the Codex in-app browser binding.
2. Call `openTabs()` and claim existing AI tabs by URL/title:
   - `yuanbao.tencent.com`
   - `doubao.com`
   - `wenxin.baidu.com`
   - `xiaohongshu.com/ai_chat` or `diandian.xiaohongshu.com`
   - `zhida.zhihu.com`
   - `qianwen.com`
   - `gemini.google.com`
   - `grok.com`
3. Confirm each claimed tab is a normal chat/search page, not a login page, CAPTCHA, 403 page, product intro page, or paywall. If login is still required, pause and ask the operator to log in manually in that tab.
4. Before submitting, read the available platform adapter notes for any selected tool:
   - `references/adapters/qianwen.md`
   - `references/adapters/diandian_xiaohongshu.md`
   - `references/adapters/zhida_zhihu.md`
   - `references/adapters/wenxin.md`
   - `references/codex_inapp_browser_troubleshooting.md`
5. Read `prompt_pack.json`. Submit prompts to the matching AI tab by `ai_tool`.
   - The first line of each generated prompt must contain `COLLECT_RUN_ID` and `PROMPT_ID`.
   - Prefer a new blank conversation for formal runs when the platform exposes a reliable new-chat action.
   - Do not append an extra marker at the end of long prompts; use the first-line marker already generated by the prompt builder.
   - Do not use generic "nearest button", "bottom button", unlabeled button, microphone button, source-count button, or coordinate-based guesses as the send action.
   - If a verified platform-specific send locator is unavailable, mark the platform as limited instead of clicking a guessed control.
6. Before sending each prompt, confirm:
   - the input box is uniquely located;
   - old content is cleared;
   - the prompt text is present in the input box or a page-level marker confirms the rich-text editor contains the prompt;
   - `PROMPT_ID` appears in the draft before sending;
   - the send action is executed through a DOM locator or confirmed keyboard action.
   - For 点点 and 文心一言, generic selector fallback is forbidden. Duplicate visible inputs or missing scoped send controls are hard failures; save `send_unconfirmed` instead of clicking a guessed control.
   - For 豆包, verify the draft through `textarea.value`; the draft may not appear in page body text.
   - For Gemini and 知乎直答, verify the rich-text editor node after clipboard paste before any send action.
7. After sending, wait for the new AI reply, save raw visible output, and extract JSON when possible.
   - The newly submitted user message must contain the current `PROMPT_ID`.
   - Input clearing alone is not proof of send success.
   - Page body text that includes a draft prompt is not proof of send success.
   - For 千问, do not capture only the text after the last `PROMPT_ID`; the page can echo the prompt after the answer. Save the full visible answer/page text after the current prompt is confirmed and let local filtering remove echoes.
8. Save outputs under:

```text
daily_ai_outputs/<run_id>/raw/
```

Recommended filename:

```text
<game_id>_<game_name>_<ai_tool>.json
```

9. Render final reports with:

```bash
python scripts/render_game_polling_reports.py daily_ai_outputs/<run_id>/game_list.json daily_ai_outputs/<run_id>/raw --output-dir daily_ai_outputs/<run_id>/reports
```

## Fast Daily Browser Order

For a 5-10 minute daily report, use this order and stop early when enough evidence is collected:

1. Claim all already-open logged-in tabs.
2. Submit Yuanbao and Doubao first.
3. Submit Qianwen if it is already logged in or if Chinese-web supplemental coverage is needed.
4. Submit one global tool: Gemini or Grok.
5. Submit Zhihu Direct Answer for controversy recap.
6. Submit DianDian with the short fallback prompt if Xiaohongshu clues are needed.
7. Submit Wenxin only when Baidu/Tieba coverage is specifically needed.

Do not wait for every tool when the report already has a usable evidence pool.

If a page's user message is not confirmed after one retry, save an error wrapper under `raw/` and continue. Do not infer success from the input box clearing.

## Strict brittle-platform contract

These rules apply to the formal Codex in-app-browser workflow:

- **点点 / 小红书**: on `https://www.xiaohongshu.com/ai_chat`, select `textarea[name="aiSearchTextarea"]`, retain visible nodes only, and require exactly one. Clear with click -> `Control+A` -> `Backspace`; fill the prompt; verify the visible textarea value contains the current `PROMPT_ID`; click exactly one visible `.ai-chat-welcome__input .submit-button-wrapper`; confirm a new `.user-message-impression-wrapper ... .user-message__text` contains the marker, then wait for `.ai-message.ai-message-finished .markdown-block` or its paragraph fallback. A placeholder such as `家庭旅行...` is not evidence of the correct input.
- **文心一言**: use `https://wenxin.baidu.com/`, select exactly one visible `textarea#chat-textarea.ci-textarea`, and use exactly one visible enabled `#ci-submit-button-ai.ci-submit-button-ai-active`. A generic `textarea` is invalid because the page can expose a second unrelated textarea. Confirm a new `.conversation-flow-question-container` contains the marker, then confirm a new `.conversation-flow-answer-container` or `.answer-box.last-answer-box`; input clearing alone is never success.
- **豆包**: use exactly one visible `textarea[placeholder="发消息..."]`. Confirm the current `PROMPT_ID` through `textarea.value`; do not fail only because `body.innerText` does not include the draft.
- **千问**: use the ordinary visible `div[role="textbox"][contenteditable="true"]`, verify editor text, submit with Enter, then save the full visible page text after current prompt confirmation. Do not slice from the last prompt marker.
- **Gemini**: use the unique visible Quill editor `div.ql-editor[contenteditable="true"][role="textbox"]`, paste through the browser clipboard, verify editor text, and never click microphone or adjacent controls as send.
- **知乎直答**: start from `https://zhida.zhihu.com/`, use the unique visible DraftEditor, verify editor text after paste, then click the rightmost input-bar send control and require a new `/search/...` route containing the current prompt.
- **Retry behavior**: each brittle platform gets at most one retry. The retry must re-check page identity, clear the old draft, re-verify the marker, and use the same scoped controls. If any uniqueness or confirmation check fails, save only a raw error wrapper with `status=error`, `send_confirmed=false`, and a concise diagnostic. Never reuse stale history as this run's response.

If the response is not strict JSON, save raw text in `response_text` and continue. The report renderer should include parseable evidence and keep the rest as limitations or pending leads.

## Evidence Rules

- Web AI output is discovery and secondary summary until URL-backed.
- Only records with a verifiable `url` may enter `evidence`.
- No-URL or unverifiable content must enter `pending_leads`.
- Never bypass login, CAPTCHA, 403, paywall, private groups, or access controls.
