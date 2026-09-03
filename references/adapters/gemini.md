# Gemini Adapter

Use this adapter when polling Gemini through the Codex in-app browser.

## 2026-07-30 v0.4.6 Diagnostic Result

- Short prompt submission succeeded.
- The page can create a new Gemini conversation route and return the expected marker string.
- The failure in long weekly runs is mainly capture quality: saving `Conversation with Gemini / You said / prompt` full-page text can miss the actual model reply.

## Current Rule

1. Verify exactly one visible Quill editor `div.ql-editor[contenteditable="true"][role="textbox"]`.
2. Clipboard-paste the current prompt and verify the editor contains `PROMPT_ID`.
3. After Enter, prefer the latest `Gemini said` / model-response text.
4. Do not save the full page, `You said` prompt echo, Flash disclaimer, or JSON schema examples as the formal reply.
5. If the targeted reply is prompt echo or placeholder-only content, save `answer_not_captured` and retry one short fallback.

## 2026-07-30 v0.4.7 Long Prompt Capture

- Gemini long prompts can show both a `user-query` prompt block and a `model-response` answer block. The answer block must win even when both contain JSON-like text.
- Prefer `model-response message-content`, `model-response .markdown`, and `message-content .markdown`; penalize `user-query`, `You said`, `Conversation with Gemini`, and any block containing the current `PROMPT_ID`.
- A saved reply should begin with the model's answer content, not with the original instruction text such as "你是游戏行业社区舆情检索助手".
- If only prompt echo is captured, retry the prompt pack's short fallback once.
