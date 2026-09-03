# DianDian / Xiaohongshu Adapter

## Saved Official Page

- Saved by user instruction on 2026-07-24: `https://www.xiaohongshu.com/ai_chat`
- Treat this URL as the current Xiaohongshu DianDian chat page.
- Entry page remains `https://www.xiaohongshu.com/`; for Xiaohongshu-related work, open Xiaohongshu first and enter DianDian from the visible `点点` navigation entry when possible.
- Accepted final route:
  - host: `www.xiaohongshu.com`
  - path: `/ai_chat`
- Historical/possible route:
  - host: `diandian.xiaohongshu.com`
  - path: `/home`

## Entry Rules

- Start from `https://www.xiaohongshu.com/`.
- Confirm the account is logged in before submitting prompts.
- Preferred entry locator: `getByRole("link", { name: /点点/ })`
- Fallback locators:
  - `a[href*="/ai_chat"]:has-text("点点")`
  - visible text `点点` near a link or button
- Do not use fixed screen coordinates.

## Page Identity

Valid DianDian page features include:

- URL is `https://www.xiaohongshu.com/ai_chat`
- title includes `小红书 - 点点`
- page text includes `想探索些什么`
- logged-in navigation markers such as `通知`, `消息`, `我`

## 2026-07-24 Route Observation

- Start URL: `https://www.xiaohongshu.com/`
- Observed home URL: `https://www.xiaohongshu.com/explore`
- Entry locator: `getByRole("link", { name: /点点/ })`
- Final URL: `https://www.xiaohongshu.com/ai_chat`
- Final host: `www.xiaohongshu.com`
- Page feature observed: `下午好，想探索些什么？`
- User later confirmed to save `www.xiaohongshu.com/ai_chat` as the DianDian page.
- Route result JSON: `D:/石声未来项目文件/游戏情报快讯/daily_ai_outputs/adapter_tests_20260724/diandian_route_result.json`

## Verified DOM Observations

Observed on `https://www.xiaohongshu.com/ai_chat` during the 2026-07-24 L5 test:

- Visible input candidates: two overlapping `textarea.textarea` nodes in `.textarea-container.ai-chat-input-box`.
- Preferred input candidate: `textarea[name="aiSearchTextarea"].textarea` with `tabIndex=0`.
- Hidden/mirror input candidate: `textarea[name="aiSearchTextarea"].textarea[tabindex="-1"][aria-hidden="true"]`; do not use this one for input verification.
- Input parent chain:
  - `.textarea-wrapper`
  - `.textarea-container.ai-chat-input-box`
  - `.wendian-wrapper.wendian-wrapper--active.wendian-wrapper--panel-down`
  - `.ai-chat-welcome__input`
- Send button wrapper: `.ai-chat-welcome__input .submit-button-wrapper`
- Fallback send locator: `.textarea-container.ai-chat-input-box .submit-button-wrapper`
- Send icon inside wrapper: `svg.reds-icon.submit-button.btn-wrapper`

## 2026-07-24 L5 Verification

- Test ID: `DIANDIANACK20260724002`
- Start URL: `https://www.xiaohongshu.com/ai_chat`
- Final URL: `https://www.xiaohongshu.com/ai_chat?conversationId=acb047f5-1d6b-40b2-9e87-9b485d064c14`
- Final level: `L5`
- Reply text: `DIANDIANACK20260724002`
- Result JSON: `D:/石声未来项目文件/游戏情报快讯/daily_ai_outputs/adapter_tests_20260724/diandian_l5_final_result_002.json`
- Screenshot: `D:/石声未来项目文件/游戏情报快讯/daily_ai_outputs/adapter_tests_20260724/diandian_l5_result_002.jpg`

Verified flow:

- Clear the `tabIndex=0` textarea with click -> Ctrl+A -> Backspace -> read value.
- Input prompt and verify textarea value contains the unique test ID.
- Send with `.ai-chat-welcome__input .submit-button-wrapper`.
- Confirm new user message via `.user-message-impression-wrapper .user-message-wrapper .user-message .user-message__text-wrapper .user-message__text`.
- Confirm AI reply via `.ai-message.ai-message-finished .markdown-block`.
- Fallback AI reply selector: `.ai-message.ai-message-finished p`.
- Streaming complete marker: `.ai-message.ai-message-finished`; also confirm absence of `生成中`, `正在回答`, `停止生成`, `思考中`, `加载中`.
- Do not use input clearing, page title, sidebar history, or sticky title as the only evidence of successful send.

## 2026-07-28 Stage 7 Retest

Observed issue in the 2026-07-28 live company report:

- The page was visible and logged in, but a long prompt remained in the visible textarea draft.
- The collector then reported `prompt_id_not_in_draft_after_fill`, `user_message_not_confirmed`, or `short_fallback_send_control_not_clickable`.
- Root cause: the executor did not consistently clear and verify the single visible textarea before selecting the send control, and it sometimes treated duplicate hidden controls as candidates.

Retest result:

- Test ID: `DIANDIAN_SEND_TEST_20260728_STAGE7`
- Input locator: `textarea[name="aiSearchTextarea"]` filtered to exactly one visible node.
- Send locator: `.ai-chat-welcome__input .submit-button-wrapper` filtered to exactly one visible node.
- Result: user message was confirmed and the AI reply contained the same test ID.

Required current flow:

1. Claim the already-open `https://www.xiaohongshu.com/ai_chat` tab when available.
2. Locate `textarea[name="aiSearchTextarea"]`, filter to visible nodes, and require exactly one visible textarea.
3. Clear any old draft before filling the prompt. A non-empty old draft is a failure risk, not harmless context.
4. Fill the prompt and verify the visible textarea value contains the current first-line `PROMPT_ID`.
5. Click only `.ai-chat-welcome__input .submit-button-wrapper` or `.textarea-container.ai-chat-input-box .submit-button-wrapper` when that locator is visible and unique.
6. Confirm the newly submitted user message through `.user-message-impression-wrapper .user-message-wrapper .user-message .user-message__text-wrapper .user-message__text`.
7. Confirm the reply through `.ai-message.ai-message-finished .markdown-block` or `.ai-message.ai-message-finished p`.
8. If the long prompt fails confirmation once, switch to the short fallback prompt and repeat the same visible-input/visible-send checks.
9. If either the visible textarea or scoped send control is not unique, save a platform limitation instead of using a generic button, duplicate hidden node, or coordinate click.

## Access Rules

- Do not bypass login, CAPTCHA, 403, paywalls, rate limits, or private content.
- Xiaohongshu evidence still requires concrete `xiaohongshu.com` or `xhslink.com` URLs.
- DianDian summaries without URLs remain `pending_leads` or secondary observations.

## 2026-07-29 v0.4.4 Capture Fix

Observed failure: opening `/ai_chat` can land on a Xiaohongshu shell where no visible `textarea[name="aiSearchTextarea"]` exists. This is not a successful chat state.

Current rule:

1. Navigate to `https://www.xiaohongshu.com/ai_chat`.
2. Wait for the page to settle, then require exactly one visible `textarea[name="aiSearchTextarea"]`.
3. If the visible textarea count is `0`, record `diandian_visible_input_not_unique:0` or `page_not_ready_for_ai_chat`; do not click generic controls.
4. If one visible textarea exists, verify `textarea.value` contains current `PROMPT_ID`, then click only `.ai-chat-welcome__input .submit-button-wrapper`.

## 2026-07-30 v0.4.6 Entry Gate

Diagnostic result: opening `https://www.xiaohongshu.com/ai_chat` can land on `https://www.xiaohongshu.com/explore` with zero visible `textarea[name="aiSearchTextarea"]`.

Current rule:

1. `/explore` with zero visible AI Chat textarea is `diandian_ai_chat_entry_not_reached`.
2. Try at most one explicit AI Chat / 点点 entry click if a visible `/ai_chat` link or clear 点点 entry exists.
3. If the textarea still does not exist, save safe DOM diagnostics and stop. Do not click generic buttons, recommendation cards, or fixed coordinates.
4. Formal evidence collection can resume only after the page is visibly in AI Chat input state with exactly one visible `textarea[name="aiSearchTextarea"]`.

## 2026-07-30 v0.4.7 Active Textarea Rule

Diagnostic result: `https://www.xiaohongshu.com/ai_chat` can correctly show the DianDian AI Chat page while exposing three `textarea[name="aiSearchTextarea"]` nodes, two of them visible and overlapping.

Current rule:

1. Multiple visible textareas are not automatically a page failure.
2. Select the active input by all of these signals: visible, not disabled, not `aria-hidden`, positive area, `tabIndex=0` preferred, and ancestor chain containing `.ai-chat-welcome__input`, `.textarea-container.ai-chat-input-box`, or `.wendian-wrapper`.
3. After selecting the candidate, clear it and verify its `value` contains the current `PROMPT_ID`.
4. Click only the scoped send control inside `.ai-chat-welcome__input` or `.textarea-container.ai-chat-input-box`.
5. If no active candidate passes these checks, save diagnostics and stop. Do not use generic buttons or screen coordinates.
