# Doubao Adapter

Use this adapter when polling Doubao through the Codex in-app browser.

## 2026-07-30 v0.4.6 Diagnostic Result

- Short prompt submission succeeded.
- The page can create a new chat route and return the expected marker string.
- The failure in long weekly runs is mainly capture quality: saving whole-page text can include sidebar history, current prompt, and JSON schema examples instead of the model answer.

## Current Rule

1. Verify exactly one visible chat textarea and confirm `textarea.value` contains the current `PROMPT_ID`.
2. After Enter, wait for the current user message and capture only the newest answer node or current-prompt answer tail.
3. Do not save whole `document.body.innerText` as the formal reply.
4. If the captured text is mostly prompt echo, JSON schema/template, old sidebar, or placeholder `https://...`, save `answer_not_captured` platform status and retry one short fallback.
5. Only current-prompt targeted answer text can enter `raw/` for structuring.

## 2026-07-30 v0.4.7 Long Prompt Capture

- Long weekly prompts can return useful answers after the initial wait window. Do not discard a visible answer merely because the page still shows streaming/generation markers.
- Prefer the newest answer candidate with structured fields such as `evidence`, `game_name`, `plain_summary`, `why_watch`, `business_use`, concrete game terms, and real URLs.
- Exclude the current prompt node, sidebar history, prompt instructions, and current `PROMPT_ID` echoes.
- If the main prompt cannot produce a valid answer node, the formal helper may retry the prompt pack's short fallback once and save the fallback raw file instead of overwriting the main raw file.
