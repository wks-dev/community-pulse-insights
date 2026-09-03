# In-App Platform Failure Matrix

This matrix is part of the formal Codex in-app-browser workflow. A failed send must never be replaced with stale history or a guessed response.

| Platform | Required send proof | Common failure | Recovery |
| --- | --- | --- | --- |
| 元宝 | Current `PROMPT_ID` in the new user message and a new stable answer/file response | Long answer still streaming or virtualized file viewer | Wait for stability; if only a file card is visible, save `response_incomplete` |
| 豆包 | New user message contains current marker and a new response container is complete | Duplicated response nodes or streaming | Scope the newest response and wait for stop state to finish |
| 文心一言 | Exactly one visible `textarea#chat-textarea.ci-textarea`; exactly one visible enabled `#ci-submit-button-ai.ci-submit-button-ai-active`; new question and answer nodes | Generic textarea selects unrelated input; compliance refusal | Return to root, use safe Chinese-public-web prompt once, then record `input_not_unique`, `send_unconfirmed`, or `compliance_refusal` |
| 豆包 | Unique visible `textarea[placeholder="发消息..."]`; `textarea.value` contains current `PROMPT_ID`; current marker appears in new conversation after Enter | Draft is present in textarea but not in `body.innerText`; hidden mirror textarea causes false failure | Verify `textarea.value`, not body text; prefer weekly expansion prompt if main prompt is too long |
| 千问 | Unique ordinary contenteditable chat box, current marker in new message, new answer route | Disabled send or AI-product-page drift | Clear and resubmit once through the ordinary chat box; mark product-page output `prompt_drift` |
| 点点 | Exactly one visible `textarea[name="aiSearchTextarea"]`; current marker in new user message; finished `.ai-message` reply | Hidden mirror or stale recommendation textarea; generic send timeout | Clear visible node, verify value, click scoped `.ai-chat-welcome__input .submit-button-wrapper`; retry one short fallback |
| 知乎直答 | New `/search/...` route and result contains current marker | Old search result remains visible | Use clean entry and the unique Draft.js editor; confirm route before saving |
| Gemini | Unique visible Quill editor contains current `PROMPT_ID`; new assistant message with current prompt and stable JSON/code block | CDP click timeout on editor, microphone/adjacent controls mistaken as send, searching state or prompt echo | Clipboard paste into the unique editor; if click translation fails, retry once with fallback and record `adapter_error` rather than clicking adjacent controls |
| Grok | New assistant response with current prompt and stable response/code | Thinking state or mixed prompt echo | Wait until stop control disappears; extract current assistant response only |

## Shared status contract

Every platform raw envelope must include `status`, `send_confirmed`, `prompt_id_confirmed`, `response_started`, `response_completed`, `response_text`, `diagnostic_text`, `source_url`, and `capture_quality`.

Use these diagnostics when applicable: `input_not_unique`, `send_control_not_unique`, `send_unconfirmed`, `user_message_not_confirmed`, `response_not_confirmed`, `response_incomplete`, `compliance_refusal`, `prompt_drift`, and `access_limited`.

Only a current-prompt response can be passed to `robust_structure_raw.py`; other envelopes remain available for audit but are rendered as platform status or limitations. If a confirmed response still contains prompt echoes or half-parsed JSON fragments, `validate_raw_capture.py` should flag it before render, and `robust_structure_raw.py` must filter debug fragments from evidence and pending leads.

## 2026-07-30 v0.4.6 Targeted Capture Addendum

- Doubao / 豆包: short diagnostics prove the page can send and answer. Formal collection must not save whole `document.body.innerText`; save only the newest answer node or current-prompt answer tail. If the captured text is mainly prompt echo, JSON schema, old sidebar, or placeholder `https://...`, record `answer_not_captured`.
- Gemini: short diagnostics prove the Quill editor can send and answer. Prefer the latest `Gemini said` / model-response text. Do not save `Conversation with Gemini`, `You said`, or full-page prompt echoes as raw evidence.
- Zhihu Direct Answer / 知乎直答: short diagnostics prove a fresh `/search/...` route can be created. Formal collection must start from `https://zhida.zhihu.com/`, confirm a new `/search/...`, and save the targeted answer region only. Old search/history text is `answer_not_captured`.
- DianDian / 点点: current diagnostics show `/ai_chat` may land on `/explore` with zero visible `textarea[name="aiSearchTextarea"]`. This is `diandian_ai_chat_entry_not_reached`, not a no-data answer. Do not use generic buttons or coordinates.
- Use `scripts/in_app_browser_diagnostics_v046.mjs` for short prompt diagnostics before changing selectors again.

## 2026-07-30 v0.4.7 Long Prompt Capture Addendum

- Doubao / 豆包: if the model visibly produces structured JSON after the first wait window, rescue the newest answer node even when the page still shows generation markers. Do not drop it just because `response_completed=false`.
- Gemini: rank model answer blocks above user prompt blocks. Penalize `user-query`, `You said`, `Conversation with Gemini`, and any node containing the current `PROMPT_ID`.
- Zhihu Direct Answer / 知乎直答: a new `/search/...` route can still answer an old task. If the captured answer is off-topic, record `answer_drift` and retry the short fallback once.
- DianDian / 点点: two overlapping visible `aiSearchTextarea` nodes can be valid. Choose the active textarea by `tabIndex=0`, non-hidden state, positive area, and AI Chat input-bar ancestry before clearing and sending.
- Automatic fallback may be used once by `submitByTool` for `answer_not_captured`, `answer_drift`, prompt echo, route failure, or user-message confirmation failure. Save fallback output with its own `fallback_prompt_id`.
- Completeness gate: for game-intelligence prompts, do not accept a short JSON head, prompt-only fallback text, or brief opening paragraph as a full answer. Require concrete game terms plus either enough length, structured fields, or real URLs.
