# Zhihu Direct Answer Adapter

Use this adapter when polling Zhihu Direct Answer through the Codex in-app browser.

## Entry

- Preferred URL: `https://zhida.zhihu.com/`
- Entry mode: `direct`
- The operator must log in manually. Do not request credentials, verification codes, cookies, tokens, local storage, or browser profile files.

## Current Failure Pattern

Observed in the 2026-07-28 company report:

- `zhida_community_deep_dive_001` succeeded.
- `zhida_company_daily_001` failed with `user_message_not_confirmed`.
- The failed main prompt was attempted while the tab was already on a `/search/...` result route.
- On that route the visible input may still exist, but send confirmation can be confused with old search history, old prompt text, or a continuing answer page.

This means login was not the main problem. The stable fix is to start formal prompts from the clean homepage route and confirm the newly created `/search/...` result.

## Page Identity

Valid ordinary page signals:

- host is `zhida.zhihu.com`;
- route is `/` before a new prompt is submitted;
- one visible `.public-DraftEditor-content[contenteditable="true"][role="textbox"]` exists;
- the page is not `/repositories` and does not show knowledge-base subscription gating.

Do not submit from:

- `/repositories`;
- a page showing `请等待文件上传完成后再进行发送`;
- a login, CAPTCHA, 403, paywall, or knowledge-base-only page.

## 2026-07-28 Stage 7 Retest

- Test ID: `ZHIDA_SEND_TEST_20260728_STAGE7`
- Start route: `https://zhida.zhihu.com/`
- Input locator: `.public-DraftEditor-content[contenteditable="true"][role="textbox"]`
- Send control: the visible clickable control in the input bar with class `r-1loqt21 r-1otgn73` whose bounding box is the rightmost control beside the editor.
- Result: page navigated to a new `/search/3743885470118967024` URL and the current test ID appeared in the new search history link.

## Required Current Flow

1. Before each formal prompt, navigate the claimed tab to `https://zhida.zhihu.com/` unless it is already on that exact route.
2. Wait for the visible DraftEditor input and require exactly one visible `.public-DraftEditor-content[contenteditable="true"][role="textbox"]`.
3. Click the editor, select all, clear, then fill or paste the prompt.
4. Verify the editor text contains the current first-line `PROMPT_ID`.
5. Locate visible `div.r-1loqt21.r-1otgn73` controls near the editor. Choose the rightmost control in the input bar, not sidebar/history controls.
6. Click that scoped rightmost control once.
7. Confirm success only when the URL changes to a new `/search/...` route and the new search/history question text contains the current `PROMPT_ID`.
8. Do not treat input clearing, old body text, or an old `/search/...` page as send confirmation.
9. If the homepage editor or rightmost input-bar send control cannot be verified, save a platform limitation and continue with other tools.

## Evidence Rule

Zhihu Direct Answer is a secondary Web AI search/summarization source. URL-backed records may enter `evidence`; URL-less prose must remain in `pending_leads` or auxiliary observations. Do not fabricate Zhihu question URLs or use placeholder `https://www.zhihu.com/question/1234567890` links.

## 2026-07-29 v0.4.4 Capture Fix

Observed failure: the DraftEditor can appear focused, but the DOM text read may not contain the pasted `PROMPT_ID`. Sending in that state risks reading an old `/search/...` result.

Current rule:

1. Always navigate to `https://zhida.zhihu.com/` before a formal prompt.
2. Use the unique visible `[contenteditable="true"][role="textbox"]`.
3. Clipboard paste the prompt and verify the editor node text contains current `PROMPT_ID`.
4. If editor text does not confirm the marker, save `zhida_prompt_id_not_in_editor_value` and do not click send.
5. After send, require a new `/search/...` route and current marker in the new result page.

## 2026-07-30 v0.4.6 Targeted Answer Capture

Diagnostic result: short prompts can create a fresh `/search/...` route and return the expected answer string.

Current rule:

1. A new `/search/...` route proves submission, but it is not enough for report raw.
2. Save only the current-prompt answer region or answer tail after the current marker.
3. If the extracted text is old history, prompt echo, or page shell, record `answer_not_captured`.
4. Never parse old search result pages, sidebar history, old prompt tests, or input-bar text into evidence.

## 2026-07-30 v0.4.7 Answer Drift Gate

Observed long-prompt failure: the page entered a new `/search/...` route, but the answer discussed an old "网页简报/文档内容" task instead of game-industry intelligence.

Current rule:

1. A new `/search/...` route proves submission only; it does not prove the answer is usable.
2. After capture, require game-intelligence signals such as 米哈游, 库洛, 原神, 绝区零, 鸣潮, 二游, 玩家, 版本, 舆情, or structured fields such as `evidence`, `game_name`, `plain_summary`, `why_watch`.
3. If the answer contains off-topic markers such as 网页简报, 文档内容, 人工智能发展简史, or 通用模板, save `answer_drift` / `zhida_answer_drift_off_topic`.
4. For formal collection, retry the prompt pack's short fallback once after `answer_drift`; do not parse the off-topic answer into evidence or pending leads.
