// Codex in-app browser collector helpers for robust-preview v0.4.4+.
// v0.4.7 hardens long-prompt reply capture and active input selection.
//
// This module is meant to be imported from the Node REPL after the Browser
// skill has created an in-app browser binding. It does not read cookies,
// tokens, local storage, or browser profiles.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const DEFAULT_TIMEOUT = 180000;

export async function createCollectorContext({ iab, runDir }) {
  if (!iab) {
    throw new Error("iab binding is required");
  }
  const packPath = path.join(runDir, "prompt_pack.json");
  const pack = JSON.parse(await readFile(packPath, "utf8"));
  await mkdir(path.join(runDir, "raw"), { recursive: true });
  return {
    iab,
    runDir,
    pack,
    tabsByTool: {},
  };
}

export async function claimTabsByTool(ctx, idByTool) {
  ctx.tabsByTool = {};
  for (const [tool, id] of Object.entries(idByTool)) {
    ctx.tabsByTool[tool] = await ctx.iab.tabs.get(id);
  }
  return ctx.tabsByTool;
}

export function promptSpec(ctx, promptId, { fallback = false } = {}) {
  const item = ctx.pack.prompts.find((prompt) => prompt.prompt_id === promptId);
  if (!item) {
    throw new Error(`prompt_not_found:${promptId}`);
  }
  if (fallback && item.fallback_prompt) {
    return {
      ai_tool: item.ai_tool,
      prompt_id: item.fallback_prompt_id || `${item.prompt_id}_fallback`,
      original_prompt_id: item.prompt_id,
      text: item.fallback_prompt,
      short_fallback: true,
      send_contract: item.fallback_send_contract || "",
    };
  }
  return {
    ai_tool: item.ai_tool,
    prompt_id: item.prompt_id,
    original_prompt_id: item.prompt_id,
    text: item.prompt,
    short_fallback: false,
    send_contract: "",
  };
}

export async function saveEnvelope(ctx, spec, envelope) {
  const effectivePromptId = envelope.prompt_id || spec.prompt_id;
  const effectiveOriginalPromptId = envelope.original_prompt_id || spec.original_prompt_id;
  const effectiveAiTool = envelope.ai_tool || spec.ai_tool;
  const isFallback = Boolean(envelope.short_fallback ?? spec.short_fallback);
  const status = envelope.status || "unknown";
  const responseText = envelope.response_text || "";
  const requestedCaptureQuality = envelope.capture_quality || "";
  const captureQuality =
    status === "ok"
      ? normalizeOkCaptureQuality(requestedCaptureQuality, responseText, Boolean(envelope.needs_structure_review))
      : requestedCaptureQuality;
  const fileStem =
    isFallback && effectiveOriginalPromptId && effectiveOriginalPromptId !== effectivePromptId
      ? `${effectiveOriginalPromptId}_fallback_${effectiveAiTool}`
      : `${effectivePromptId}_${effectiveAiTool}`;
  const fileName = `${fileStem}.json`.replace(/[\\/:*?"<>|]/g, "_");
  const file = path.join(ctx.runDir, "raw", fileName);
  const payload = {
    prompt_id: effectivePromptId,
    original_prompt_id: effectiveOriginalPromptId,
    original_failed_prompt_id: envelope.original_failed_prompt_id || "",
    ai_tool: effectiveAiTool,
    short_fallback: isFallback,
    submitted_at: envelope.submitted_at || "",
    retrieved_at: new Date().toISOString(),
    status,
    send_confirmed: Boolean(envelope.send_confirmed),
    prompt_id_confirmed: Boolean(envelope.prompt_id_confirmed),
    response_started: Boolean(envelope.response_started),
    response_completed: Boolean(envelope.response_completed),
    source_url: envelope.source_url || "",
    capture_mode: envelope.capture_mode || "",
    answer_confirmed: envelope.answer_confirmed ?? true,
    valid_answer: Object.prototype.hasOwnProperty.call(envelope, "valid_answer") ? envelope.valid_answer : undefined,
    needs_human_review: Boolean(envelope.needs_human_review),
    candidate_score: envelope.candidate_score ?? undefined,
    candidate_reason: envelope.candidate_reason || "",
    capture_quality: captureQuality,
    capture_quality_detail: requestedCaptureQuality,
    needs_structure_review: Boolean(envelope.needs_structure_review ?? status === "ok"),
    error: envelope.error || "",
    diagnostic_text: envelope.diagnostic_text || "",
    response_text: responseText,
  };
  await writeFile(file, JSON.stringify(payload, null, 2), "utf8");
  return file;
}

function normalizeOkCaptureQuality(captureQuality, responseText, needsReview) {
  const quality = String(captureQuality || "").trim().toLowerCase();
  if (["weak", "normal", "strong"].includes(quality)) {
    return quality;
  }
  if (looksLikePlaceholderPromptTemplate(responseText)) {
    return "weak";
  }
  if (needsReview || /answer_not_captured|answer_drift|prompt_echo|incomplete|weak/i.test(quality)) {
    return "weak";
  }
  const text = String(responseText || "");
  if (hasRealUrl(text) || hasStructuredEvidenceSignal(text) || text.length >= 800) {
    return "strong";
  }
  return "normal";
}

export async function saveFailure(ctx, spec, error, tab, captureQuality = "adapter_error") {
  const sourceUrl = tab ? await tab.url().catch(() => "") : "";
  return saveEnvelope(ctx, spec, {
    status: "error",
    send_confirmed: false,
    prompt_id_confirmed: false,
    response_started: false,
    response_completed: false,
    source_url: sourceUrl,
    capture_quality: captureQuality,
    error: String(error?.message || error),
    diagnostic_text: String(error?.stack || error),
    response_text: "",
  });
}

async function bodyText(tab, limit = 120000) {
  return tab.playwright.evaluate(
    (max) => (document.body?.innerText || "").slice(-max),
    limit,
    { timeoutMs: 15000 },
  );
}

async function visibleCount(locator) {
  return locator.filter({ visible: true }).count();
}

async function clearAndPaste(tab, locator, text) {
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(`input_not_unique:${count}`);
  }
  await locator.click({ timeoutMs: 10000 });
  await locator.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
  await locator.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
  try {
    await locator.fill(text, { timeoutMs: 20000 });
  } catch {
    await tab.clipboard.writeText(text);
    await locator.click({ timeoutMs: 10000 });
    await locator.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
    await locator.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
    await locator.press("Control+V", { timeoutMs: 20000 });
  }
  await tab.playwright.waitForTimeout(800);
}

async function clearAndPasteContentEditable(tab, locator, text) {
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(`input_not_unique:${count}`);
  }
  await locator.click({ timeoutMs: 10000 });
  await locator.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
  await locator.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
  await tab.clipboard.writeText(text);
  await locator.press("Control+V", { timeoutMs: 20000 });
  await tab.playwright.waitForTimeout(800);
}

async function valueOf(locator) {
  return locator.evaluate(
    (el) => el.value || el.innerText || el.textContent || "",
    null,
    { timeoutMs: 5000 },
  );
}

async function waitForStableCurrentPrompt(tab, promptId, timeoutMs = DEFAULT_TIMEOUT) {
  const startedAt = Date.now();
  let last = "";
  let stableCount = 0;
  let seen = false;
  while (Date.now() - startedAt < timeoutMs) {
    const text = await bodyText(tab).catch(() => "");
    const first = text.indexOf(promptId);
    if (first >= 0) {
      seen = true;
      const tail = text.slice(first);
      if (tail === last && tail.length > promptId.length + 120) {
        stableCount += 1;
      } else {
        stableCount = 0;
      }
      last = tail;
      if (stableCount >= 2 && !/正在|生成中|停止生成|Thinking|Generating|搜索中|思考中/.test(tail)) {
        return { seen, completed: true, text };
      }
    }
    await tab.playwright.waitForTimeout(4000);
  }
  return { seen, completed: false, text: await bodyText(tab).catch(() => "") };
}

function envelopeFromWait(spec, tab, waited, submittedAt, captureQuality) {
  const responseText = waited.text || "";
  return {
    submitted_at: submittedAt,
    status: waited.seen ? "ok" : "error",
    send_confirmed: waited.seen,
    prompt_id_confirmed: waited.seen,
    response_started: responseText.length > spec.text.length + 120,
    response_completed: waited.completed,
    response_text: responseText,
    source_url: "",
    capture_quality: captureQuality,
    error: waited.seen ? "" : "user_message_not_confirmed",
  };
}

function countNeedle(text, needle) {
  if (!needle) {
    return 0;
  }
  return String(text || "").split(needle).length - 1;
}

function textHash(text) {
  const value = String(text || "");
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function hasRealUrl(text) {
  return /https?:\/\/(?!\.\.\.)[^\s\])"'，。；、]+/i.test(String(text || ""));
}

function countMatches(text, patterns) {
  const value = String(text || "");
  return patterns.reduce((count, pattern) => count + (pattern.test(value) ? 1 : 0), 0);
}

function hasGameIntelSignal(text) {
  return /米哈游|库洛|原神|绝区零|崩坏|星穹铁道|鸣潮|战双|二游|二次元游戏|玩家|版本|抽卡|回流|退坑|舆情|小红书|知乎|微博|B站|NGA|Genshin|Honkai|Zenless|Wuthering/i.test(String(text || ""));
}

function hasStructuredEvidenceSignal(text) {
  return /"evidence"\s*:|"game_name"\s*:|"plain_summary"\s*:|"why_watch"\s*:|"business_use"\s*:|证据|玩家|风险等级|公开链接|URL/i.test(String(text || ""));
}

function promptTemplateMarkerCount(text) {
  const value = String(text || "");
  const markers = [
    "帖子/视频/问答/新闻/公告标题",
    "帖子 / 视频 / 问答 / 新闻 / 公告标题",
    "YYYY-MM-DD 或可核查的相对时间",
    "只基于证据的一句话说明",
    "这件事是什么，用大白话说明",
    "玩家对剧情、角色、玩法、优化、付费或运营的具体意见",
    "为什么今天值得关注",
    "可以拿去和客户或内部业务聊什么",
    "core_evidence | auxiliary_sample | pending_lead",
    "accessible | search_snippet_only",
    "无URL、待验证或访问受限的线索",
    "本周期没有找到具体公开信息/社区讨论",
    "AI 工具产品页、API 页、下载页、介绍页必须判定为 prompt_drift",
  ];
  return markers.filter((marker) => value.includes(marker)).length;
}

function looksLikePlaceholderPromptTemplate(text) {
  return promptTemplateMarkerCount(text) >= 3;
}

function looksLikePromptInstruction(text) {
  const value = String(text || "");
  const markers = [
    "AUTOMATION_MARKER",
    "COLLECT_RUN_ID=",
    "PROMPT_ID=",
    "你是游戏行业社区舆情检索助手",
    "工具身份防漂移",
    "请忽略历史对话",
    "检索目标关键词",
    "平台/工具专项",
    "当前 AI 工具",
    "输出必须是严格 JSON",
    "每个命中项至少返回",
    "硬性要求",
    "当前 Web AI 工具",
    "You said",
    "Conversation with Gemini",
  ];
  const markerHits = markers.filter((marker) => value.includes(marker)).length;
  return markerHits >= 1;
}

function looksLikeOffTopicAnswer(text, spec) {
  const value = String(text || "");
  if (!/游戏行业|米哈游|库洛|二游|原神|绝区零|鸣潮|Honkai|Genshin|Wuthering/i.test(String(spec?.text || ""))) {
    return false;
  }
  const offTopicMarkers = [
    "网页简报",
    "产品简报",
    "文档内容",
    "人工智能发展简史",
    "没有提供具体的文档",
    "生成一份网页",
    "HTML代码",
    "品牌形象页面",
    "AI搜索能力",
    "知乎直答 ·",
    "通用模板",
  ];
  if (offTopicMarkers.some((marker) => value.includes(marker))) {
    return true;
  }
  return value.length > 300 && !hasGameIntelSignal(value) && (!hasStructuredEvidenceSignal(value) || /zhstatic|stylesheet|<html|<head|<body/i.test(value));
}

function isGameIntelSpec(spec) {
  return /游戏行业|米哈游|库洛|二游|二次元游戏|原神|绝区零|鸣潮|Honkai|Genshin|Wuthering/i.test(String(spec?.text || ""));
}

function looksLikeJsonTemplateOrPromptEcho(text, spec) {
  const value = String(text || "");
  const promptCount = countNeedle(value, spec.prompt_id);
  const templateMarkers = [
    "帖子/视频/问答/新闻/公告标题",
    "帖子 / 视频 / 问答 / 新闻 / 公告标题",
    "只基于证据的一句话说明",
    "这件事是什么，用大白话说明",
    "https://...",
    "COLLECT_RUN_ID=",
    "AUTOMATION_MARKER",
  ];
  const hasTemplate = templateMarkers.some((marker) => value.includes(marker));
  const hasConcreteShape = hasRealUrl(value) || hasStructuredEvidenceSignal(value) || /(^|\n)\s*\d{1,2}[.、)]\s*\S/.test(value) || /公司[:：]|游戏名[:：]|事件标题[:：]|标题或事件[:：]|公开链接[:：]/.test(value);
  if (looksLikePlaceholderPromptTemplate(value)) {
    return true;
  }
  if (promptCount > 1) {
    return true;
  }
  if (looksLikePromptInstruction(value)) {
    return true;
  }
  if (hasTemplate && !hasConcreteShape) {
    return true;
  }
  if (value.trim().length <= Math.min(180, Math.floor((spec.text || "").length * 0.08)) && !hasConcreteShape) {
    return true;
  }
  return false;
}

function captureQualityGate(spec, responseText) {
  const text = String(responseText || "").trim();
  if (!text) {
    return { ok: false, error: "empty_reply_node" };
  }
  if (/输入你的问题，或使用|^\s*搜索\s*Ctrl\s*K\s*$/s.test(text)) {
    return { ok: false, error: "page_chrome_not_answer" };
  }
  if (looksLikeJsonTemplateOrPromptEcho(text, spec)) {
    return { ok: false, error: "reply_node_not_confirmed_or_prompt_echo" };
  }
  if (text === spec.text || text.includes(spec.text.slice(0, Math.min(500, spec.text.length))) && text.length < spec.text.length + 120) {
    return { ok: false, error: "answer_not_captured_prompt_echo" };
  }
  if (isGameIntelSpec(spec) && text.length < 500 && !hasGameIntelSignal(text) && !hasRealUrl(text)) {
    return { ok: false, error: "answer_incomplete_no_game_signal" };
  }
  if (isGameIntelSpec(spec) && text.length < 300 && !hasStructuredEvidenceSignal(text) && !hasRealUrl(text)) {
    return { ok: false, error: "answer_incomplete_too_short" };
  }
  if (isGameIntelSpec(spec) && text.includes('"evidence"') && !/"game_name"\s*:/.test(text) && !hasRealUrl(text)) {
    return { ok: false, error: "answer_incomplete_json_head_only" };
  }
  if (looksLikeOffTopicAnswer(text, spec)) {
    return { ok: false, error: "answer_drift_off_topic" };
  }
  return { ok: true, error: "" };
}

async function visiblePageDiagnostics(tab) {
  return tab.playwright.evaluate(() => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const brief = (el, index) => {
      const r = el.getBoundingClientRect();
      return {
        index,
        tag: el.tagName,
        role: el.getAttribute("role") || "",
        name: el.getAttribute("name") || "",
        placeholder: el.getAttribute("placeholder") || "",
        cls: String(el.className || "").slice(0, 120),
        text: (el.innerText || el.textContent || "").trim().slice(0, 120),
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      };
    };
    return {
      url: location.href,
      title: document.title,
      textareas: Array.from(document.querySelectorAll("textarea")).filter(visible).map(brief),
      editors: Array.from(document.querySelectorAll('[contenteditable="true"], [role="textbox"]')).filter(visible).map(brief),
      buttons: Array.from(document.querySelectorAll('button,[role="button"],.submit-button-wrapper,div.r-1loqt21.r-1otgn73')).filter(visible).slice(0, 30).map(brief),
      bodyTail: (document.body?.innerText || "").slice(-1200),
    };
  }, null, { timeoutMs: 15000 });
}

async function captureCandidateTexts(tab, selectors) {
  return tab.playwright.evaluate((selectorList) => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const out = [];
    for (const selector of selectorList) {
      for (const el of Array.from(document.querySelectorAll(selector))) {
        if (!visible(el)) {
          continue;
        }
        const text = (el.innerText || el.textContent || "").trim();
        if (text.length >= 8) {
          const r = el.getBoundingClientRect();
          out.push({
            selector,
            tag: el.tagName,
            className: String(el.className || "").slice(0, 160),
            testId: el.getAttribute("data-testid") || "",
            text,
            rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
          });
        }
      }
    }
    return out.slice(-30);
  }, selectors, { timeoutMs: 15000 }).catch(() => []);
}

function textAfterPrompt(text, promptId) {
  const value = String(text || "");
  const index = value.lastIndexOf(promptId);
  if (index < 0) {
    return "";
  }
  return value.slice(index + promptId.length).trim();
}

const STRUCTURED_ANSWER_START_RE = /(?:^|\n)\s*(?:(?:\d{1,2}|[一二三四五六七八九十])[.\u3001:：-]?\s*)?(?:游戏名|game_name)\s*[:：]/giu;

function promptIndexes(text, promptId) {
  const value = String(text || "");
  const id = String(promptId || "");
  const indexes = [];
  if (!id) {
    return indexes;
  }
  let offset = 0;
  while (offset < value.length) {
    const index = value.indexOf(id, offset);
    if (index < 0) {
      break;
    }
    indexes.push(index);
    offset = index + id.length;
  }
  return indexes;
}

function cutBeforeNextPromptMarker(text) {
  const value = String(text || "");
  const next = value.search(/\n\s*(?:PROMPT_ID=|AUTOMATION_MARKER|COLLECT_RUN_ID=)/);
  if (next > 200) {
    return value.slice(0, next);
  }
  return value;
}

function collectPromptTailCandidates(pageText, spec) {
  const value = String(pageText || "");
  const indexes = promptIndexes(value, spec?.prompt_id || "");
  const out = [];
  for (const index of indexes) {
    const rawTail = value.slice(index + String(spec.prompt_id).length);
    const nextPrompt = rawTail.search(/\n\s*PROMPT_ID=/);
    const area = compactRescueText(nextPrompt > 200 ? rawTail.slice(0, nextPrompt) : rawTail);
    if (area.length >= 80) {
      out.push({ source: "__body_prompt_tail", text: area });
    }
    const matches = Array.from(area.matchAll(STRUCTURED_ANSWER_START_RE));
    for (const match of matches) {
      const segment = compactRescueText(cutBeforeNextPromptMarker(area.slice(match.index)));
      if (segment.length >= 80) {
        out.push({ source: "__body_structured_answer_segment", text: segment });
      }
    }
  }
  const deduped = [];
  const seen = new Set();
  for (const item of out) {
    const hash = textHash(item.text.slice(0, 12000));
    if (seen.has(hash)) {
      continue;
    }
    seen.add(hash);
    deduped.push({ ...item, hash, is_new: true, selector: item.source, className: "", testId: "" });
  }
  return deduped.slice(-12);
}

function bestPromptTailCandidate(pageText, spec, tool) {
  const ranked = collectPromptTailCandidates(pageText, spec)
    .map((item) => scoreAnswerRescueCandidate(spec, item, tool, null))
    .sort((a, b) => b.score - a.score);
  const best = ranked[0];
  if (best && !best.disqualified && best.score >= 45) {
    return best.text;
  }
  return "";
}

function replyScore(spec, item, tool) {
  const text = String(item?.text || "");
  if (!text.trim()) {
    return -999;
  }
  let score = Math.min(40, Math.floor(text.length / 250));
  if (hasStructuredEvidenceSignal(text)) score += 35;
  if (hasGameIntelSignal(text)) score += 25;
  if (hasRealUrl(text)) score += 15;
  if (/^\s*(JSON\s*)?\{/.test(text)) score += 12;
  if (/搜索\s*\d+\s*个关键词|参考\s*\d+\s*篇资料/.test(text)) score += 10;
  if (tool === "Gemini" && /model-response|message-content/i.test(`${item?.selector || ""} ${item?.tag || ""}`)) score += 20;
  if (tool === "Gemini" && /user-query|You said|Conversation with Gemini/i.test(`${item?.selector || ""} ${text.slice(0, 160)}`)) score -= 80;
  if (tool === "知乎直答" && /zhida_answer_result_block/i.test(`${item?.selector || ""} ${item?.testId || ""}`)) score += 120;
  if (tool === "知乎直答" && /zhida_input_box|InputLike|Editable-content/i.test(`${item?.selector || ""} ${item?.testId || ""} ${item?.className || ""}`)) score -= 160;
  if (/输入你的问题，或使用/.test(text)) score -= 180;
  if (String(item?.selector || "").includes("query-text")) score -= 80;
  if (text.includes(spec.prompt_id)) score -= 120;
  if (looksLikePromptInstruction(text)) score -= 140;
  if (looksLikeOffTopicAnswer(text, spec)) score -= 120;
  const gate = captureQualityGate(spec, text);
  if (!gate.ok) score -= 80;
  return score;
}

const RESCUE_GAME_PATTERNS = [
  /原神|Genshin/i,
  /绝区零|Zenless|ZZZ/i,
  /崩坏[:：]?\s*星穹铁道|星穹铁道|Honkai[:：]?\s*Star\s*Rail|HSR/i,
  /崩坏3|Honkai\s*Impact/i,
  /鸣潮|Wuthering\s*Waves/i,
  /战双帕弥什|Punishing[:：]?\s*Gray\s*Raven|PGR/i,
  /恋与深空|Love\s*and\s*Deepspace/i,
  /未定事件簿|Tears\s*of\s*Themis/i,
  /明日方舟|Arknights/i,
  /少前2|少女前线|Girls[’']?\s*Frontline/i,
  /尘白禁区|Snowbreak/i,
  /碧蓝航线|Azur\s*Lane/i,
  /阴阳师|Onmyoji/i,
  /FGO|命运冠位指定/i,
  /因缘精灵|星布谷地|蓝色星原|无限大|异环|二重螺旋|重返未来|1999|鸣式/i,
];

const RESCUE_FEEDBACK_PATTERNS = [
  /抽卡|卡池|保底|氪金|付费/,
  /退坑|弃坑|回流|留存|长草/,
  /剧情|角色|人设|配音|立绘/,
  /版本|活动|更新|优化|修复/,
  /争议|节奏|舆情|吐槽|炎上/,
  /观望|好评|差评|玩家反馈|社区反馈/,
];

const RESCUE_STRUCTURE_PATTERNS = [
  /(^|\n)\s*(?:\d{1,2}[.、)]|[-*+]\s+)\S/,
  /\|[^|\n]{2,}\|[^|\n]{2,}\|/,
  /\b(?:game_name|plain_summary|why_watch|business_use|evidence|pending_lead|auxiliary_sample)\b/i,
  /(?:游戏|事件|标题|链接|URL|玩家反馈|舆情|来源|摘要|原因|平台)\s*[:：]/,
  /^\s*\{[\s\S]*\}\s*$/,
];

const RESCUE_PROMPT_MARKER_PATTERNS = [
  /PROMPT_ID|COLLECT_RUN_ID|AUTOMATION_MARKER/,
  /输出必须|只返回|JSON\s*schema|严格\s*JSON|工具身份防漂移/i,
  /帖子\s*\/\s*视频\s*\/\s*问答|accessible\s*\|\s*search_snippet_only/i,
];

const RESCUE_PAGE_SHELL_PATTERNS = [
  /新建对话|最近对话|历史记录|对话历史|我的空间|工具区|更多工具/,
  /下载|分享|复制|重新生成|停止生成|清空上下文|上传文件|联网搜索/,
  /登录|会员|开通|API\s*服务|插件|应用中心|模型选择/,
  /PPT创作|AI生图|AI搜索|智能体|技能广场|创作中心/,
  /请输入|输入你的问题|问我任何问题|Ask me anything|Start a new chat/i,
  /内容由AI生成|AI也可能会犯错|AI\s+can\s+make\s+mistakes/i,
];

const RESCUE_HISTORY_PATTERNS = [
  /昨天|今天|前天|Earlier|Yesterday|Today|Previous chat/i,
  /历史消息|历史对话|继续上次|最近使用|搜索历史/,
  /以下是历史|之前的回答|上一轮|上次提到/,
];

function uniqueStrings(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function rescueSelectorsFor(tool) {
  const selectorMap = {
    "元宝": [
      ".agent-chat__list",
      ".hyc-component-reasoner__text",
      ".hyc-markdown",
      ".markdown-body",
      '[class*="agent"]',
      '[class*="answer"]',
      '[class*="message"]',
    ],
    Grok: [
      '[data-testid*="message"]',
      '[class*="message"]',
      '[class*="response"]',
      '[class*="markdown"]',
    ],
    "文心一言": [
      ".answer",
      ".markdown",
      ".chat-message",
      ".ci-chat-message",
      '[class*="answer"]',
      '[class*="message"]',
    ],
    "千问": [
      '[class*="message"]',
      '[class*="markdown"]',
      '[data-testid*="message"]',
      '[class*="answer"]',
    ],
    "豆包": [
      '[data-testid*="message"]',
      '[class*="message"]',
      '[class*="Message"]',
      '[class*="markdown"]',
      '[class*="answer"]',
      '[class*="bot"]',
    ],
    "点点": [
      ".ai-message.ai-message-finished .markdown-block",
      ".ai-message.ai-message-finished p",
      ".ai-message.ai-message-finished",
      '[class*="markdown"]',
    ],
    "知乎直答": [
      '[data-testid="Block:zhida_answer_result_block"]',
      ".Render-markdown",
      '[data-testid*="answer"]',
      '[class*="Answer"]',
      '[class*="answer"]',
      '[class*="markdown"]',
      '[class*="RichText"]',
    ],
  };
  const general = [
    "article",
    "main",
    '[role="article"]',
    '[data-testid*="conversation"]',
    '[data-testid*="answer"]',
    '[data-testid*="response"]',
    '[class*="conversation"]',
    '[class*="chat"]',
    '[class*="reply"]',
    '[class*="answer"]',
    '[class*="response"]',
    '[class*="markdown"]',
    '[class*="message"]',
  ];
  return uniqueStrings([...(selectorMap[tool] || []), ...general]);
}

function compactRescueText(text) {
  return String(text || "")
    .replace(/\r/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim()
    .slice(0, 18000);
}

function hasUrlOrNoUrl(text) {
  const value = String(text || "");
  return /https?:\/\/(?!\.\.\.)[^\s\])"']+/i.test(value) || /\bno_url\b|无URL|无链接|待验证|待核验|访问受限|搜索片段/i.test(value);
}

function rescueGameSignalCount(text) {
  const value = String(text || "");
  const localSignals = RESCUE_GAME_PATTERNS.filter((pattern) => pattern.test(value)).length;
  return localSignals + (hasGameIntelSignal(value) ? 1 : 0);
}

function rescueFeedbackSignalCount(text) {
  return countMatches(text, RESCUE_FEEDBACK_PATTERNS);
}

function rescueStructuredSignalCount(text) {
  const value = String(text || "");
  return countMatches(value, RESCUE_STRUCTURE_PATTERNS) + (hasStructuredEvidenceSignal(value) ? 1 : 0);
}

function rescuePromptMarkerCount(text, spec) {
  const value = String(text || "");
  return (
    countNeedle(value, spec?.prompt_id || "") +
    countMatches(value, RESCUE_PROMPT_MARKER_PATTERNS) +
    promptTemplateMarkerCount(value)
  );
}

function scoreAnswerRescueCandidate(spec, item, tool, beforeSnapshot = null) {
  const text = compactRescueText(item?.text || "");
  const hash = item?.hash || textHash(text);
  const beforeHashes = new Set(beforeSnapshot?.candidate_hashes || []);
  const length = text.length;
  const gameSignals = rescueGameSignalCount(text);
  const feedbackSignals = rescueFeedbackSignalCount(text);
  const structuredSignals = rescueStructuredSignalCount(text);
  const promptMarkers = rescuePromptMarkerCount(text, spec);
  const shellMarkers = countMatches(text, RESCUE_PAGE_SHELL_PATTERNS);
  const historyMarkers = countMatches(text, RESCUE_HISTORY_PATTERNS);
  const hasUrlSignal = hasUrlOrNoUrl(text);
  const isNewNode = Boolean(item?.is_new ?? !beforeHashes.has(hash));
  const source = String(item?.source || item?.selector || "");
  let score = 0;
  const reasons = [];

  if (isNewNode) {
    score += 25;
    reasons.push("new_node_or_tail");
  }
  if (length >= 180 && length <= 12000) {
    score += 20;
    reasons.push("reasonable_length");
  } else if (length >= 80) {
    score += 8;
    reasons.push("short_but_nonempty");
  } else {
    score -= 45;
    reasons.push("too_short");
  }
  if (gameSignals > 0) {
    score += 28 + Math.min(18, gameSignals * 4);
    reasons.push(`game_signal:${gameSignals}`);
  }
  if (feedbackSignals > 0) {
    score += 18 + Math.min(12, feedbackSignals * 3);
    reasons.push(`feedback_signal:${feedbackSignals}`);
  }
  if (hasUrlSignal) {
    score += 18;
    reasons.push("url_or_no_url");
  }
  if (structuredSignals > 0) {
    score += 20 + Math.min(15, structuredSignals * 3);
    reasons.push(`structured_signal:${structuredSignals}`);
  }
  if (/__body_after_prompt|message|answer|response|markdown|article/i.test(source)) {
    score += 8;
    reasons.push("answer_like_source");
  }

  if (promptMarkers > 0) {
    score -= 35 * promptMarkers;
    reasons.push(`prompt_marker:${promptMarkers}`);
  }
  if (looksLikePromptInstruction(text)) {
    score -= 80;
    reasons.push("prompt_instruction");
  }
  if (looksLikePlaceholderPromptTemplate(text)) {
    score -= 90;
    reasons.push("schema_template");
  }
  if (shellMarkers > 0) {
    score -= 24 * shellMarkers;
    reasons.push(`page_shell:${shellMarkers}`);
  }
  if (historyMarkers > 0) {
    score -= 26 * historyMarkers;
    reasons.push(`history_mix:${historyMarkers}`);
  }
  if (length > 18000) {
    score -= 60;
    reasons.push("too_long_possible_full_page");
  }
  if (gameSignals === 0 && feedbackSignals === 0 && structuredSignals === 0 && !hasUrlSignal) {
    score -= 65;
    reasons.push("no_answer_signal");
  }
  if (looksLikeOffTopicAnswer(text, spec)) {
    score -= 75;
    reasons.push("off_topic");
  }

  const disqualified =
    !text ||
    (length < 80 && gameSignals === 0 && !hasUrlSignal) ||
    (promptMarkers >= 2 && gameSignals === 0) ||
    (shellMarkers >= 3 && gameSignals === 0 && structuredSignals === 0) ||
    (historyMarkers >= 2 && gameSignals === 0 && !hasUrlSignal);

  return {
    ...item,
    text,
    hash,
    score,
    reasons,
    reason: reasons.join(";"),
    disqualified,
  };
}

function selectAnswerRescueCandidate(spec, tool, beforeSnapshot, candidates) {
  const ranked = (candidates || [])
    .map((item) => scoreAnswerRescueCandidate(spec, item, tool, beforeSnapshot))
    .sort((a, b) => b.score - a.score);
  const best = ranked[0] || null;
  if (!best || best.disqualified || best.score < 45) {
    return {
      matched: false,
      best_score: best?.score ?? null,
      best_reason: best?.reason || "no_candidate",
      ranked: ranked.slice(0, 5).map((item) => ({
        selector: item.selector || item.source || "",
        score: item.score,
        reason: item.reason,
        text_hash: item.hash,
        text_chars: item.text.length,
      })),
    };
  }
  return {
    matched: true,
    text: best.text,
    score: best.score,
    reason: best.reason,
    selector: best.selector || best.source || "",
    text_hash: best.hash,
    ranked: ranked.slice(0, 5).map((item) => ({
      selector: item.selector || item.source || "",
      score: item.score,
      reason: item.reason,
      text_hash: item.hash,
      text_chars: item.text.length,
    })),
  };
}

async function capturePageSnapshot(tab, spec, tool) {
  const [url, pageText, nodeInfo] = await Promise.all([
    tab.url().catch(() => ""),
    bodyText(tab, 120000).catch(() => ""),
    tab.playwright.evaluate((promptId) => {
      const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
      const unique = (selectors) => {
        const seen = new Set();
        const out = [];
        for (const selector of selectors) {
          for (const el of Array.from(document.querySelectorAll(selector))) {
            if (!visible(el) || seen.has(el)) {
              continue;
            }
            seen.add(el);
            out.push((el.innerText || el.textContent || "").trim());
          }
        }
        return out.filter(Boolean);
      };
      const userTexts = unique([
        '[data-testid*="user"]',
        '[class*="user"]',
        '[class*="User"]',
        '[class*="query"]',
        '[class*="Question"]',
        ".user-query",
        ".human-message",
      ]);
      const aiTexts = unique([
        '[data-testid*="assistant"]',
        '[data-testid*="answer"]',
        '[data-testid*="response"]',
        '[class*="assistant"]',
        '[class*="answer"]',
        '[class*="response"]',
        '[class*="markdown"]',
        '[class*="bot"]',
        ".ai-message",
        ".model-response-text",
        "model-response",
      ]);
      return {
        user_texts: userTexts.slice(-20),
        ai_texts: aiTexts.slice(-30),
        user_message_count: userTexts.length,
        ai_reply_count: aiTexts.length,
        user_prompt_seen: userTexts.some((text) => text.includes(promptId)),
        ai_prompt_seen: aiTexts.some((text) => text.includes(promptId)),
      };
    }, spec.prompt_id, { timeoutMs: 15000 }).catch(() => ({
      user_texts: [],
      ai_texts: [],
      user_message_count: 0,
      ai_reply_count: 0,
      user_prompt_seen: false,
      ai_prompt_seen: false,
    })),
  ]);
  const candidates = await captureCandidateTexts(tab, rescueSelectorsFor(tool));
  return {
    url,
    tool,
    prompt_seen: pageText.includes(spec.prompt_id),
    user_prompt_seen: Boolean(nodeInfo.user_prompt_seen),
    ai_prompt_seen: Boolean(nodeInfo.ai_prompt_seen),
    user_message_count: nodeInfo.user_message_count || 0,
    ai_reply_count: nodeInfo.ai_reply_count || 0,
    body_tail_hash: textHash(pageText.slice(-4000)),
    user_message_hashes: uniqueStrings((nodeInfo.user_texts || []).map((text) => textHash(compactRescueText(text).slice(0, 12000)))),
    ai_reply_hashes: uniqueStrings((nodeInfo.ai_texts || []).map((text) => textHash(compactRescueText(text).slice(0, 12000)))),
    candidate_hashes: uniqueStrings(candidates.map((item) => textHash(compactRescueText(item.text).slice(0, 12000)))),
    candidate_count: candidates.length,
  };
}

async function captureAnswerRescueCandidates(tab, spec, tool, beforeSnapshot) {
  const pageText = await bodyText(tab, 120000).catch(() => "");
  const candidates = await captureCandidateTexts(tab, rescueSelectorsFor(tool));
  const beforeHashes = new Set(beforeSnapshot?.candidate_hashes || []);
  const out = [];
  for (const item of candidates) {
    const text = compactRescueText(item.text);
    const hash = textHash(text.slice(0, 12000));
    out.push({
      ...item,
      text,
      hash,
      is_new: !beforeHashes.has(hash),
      source: "candidate_node",
    });
  }
  const tail = compactRescueText(textAfterPrompt(pageText, spec.prompt_id));
  if (tail) {
    const hash = textHash(tail.slice(0, 12000));
    out.push({
      selector: "__body_after_prompt",
      source: "__body_after_prompt",
      text: tail,
      hash,
      is_new: true,
      className: "",
      testId: "",
    });
  }
  for (const item of collectPromptTailCandidates(pageText, spec)) {
    out.push(item);
  }
  const deduped = [];
  const seen = new Set();
  for (const item of out) {
    if (!item.hash || seen.has(item.hash)) {
      continue;
    }
    seen.add(item.hash);
    deduped.push(item);
  }
  return deduped.slice(-40);
}

function promptConfirmedAfterSend(beforeSnapshot, afterSnapshot, waited) {
  if (!afterSnapshot?.prompt_seen) {
    return false;
  }
  const beforeUserHashes = new Set(beforeSnapshot?.user_message_hashes || []);
  const hasNewUserHash = (afterSnapshot.user_message_hashes || []).some((hash) => !beforeUserHashes.has(hash));
  const userCountIncreased = (afterSnapshot.user_message_count || 0) > (beforeSnapshot?.user_message_count || 0);
  if (afterSnapshot.user_prompt_seen && (!beforeSnapshot?.user_prompt_seen || hasNewUserHash || userCountIncreased)) {
    return true;
  }
  const bodyChanged = beforeSnapshot?.body_tail_hash && afterSnapshot.body_tail_hash !== beforeSnapshot.body_tail_hash;
  const aiCountIncreased = (afterSnapshot.ai_reply_count || 0) > (beforeSnapshot?.ai_reply_count || 0);
  return Boolean(waited?.seen && bodyChanged && aiCountIncreased);
}

async function answerRescue(tab, spec, tool, beforeSnapshot, waited) {
  const afterSnapshot = await capturePageSnapshot(tab, spec, tool).catch((error) => ({
    snapshot_error: String(error?.message || error),
    prompt_seen: false,
  }));
  const promptConfirmed = promptConfirmedAfterSend(beforeSnapshot, afterSnapshot, waited);
  if (!promptConfirmed) {
    return {
      matched: false,
      reason: "rescue_prompt_not_confirmed_after_send",
      afterSnapshot,
    };
  }
  const candidates = await captureAnswerRescueCandidates(tab, spec, tool, beforeSnapshot);
  const selected = selectAnswerRescueCandidate(spec, tool, beforeSnapshot, candidates);
  return {
    ...selected,
    afterSnapshot,
    candidate_count: candidates.length,
  };
}

function shouldAttemptAnswerRescue(envelope, spec) {
  if (envelope?.capture_mode === "rescue_candidate") {
    return false;
  }
  if (!envelope || envelope.status !== "ok") {
    return true;
  }
  const text = String(envelope.response_text || "");
  const gate = captureQualityGate(spec, text);
  if (!text.trim() || !gate.ok) {
    return true;
  }
  return /answer_not_captured|prompt_echo|reply_not_started|route_not_confirmed|user_message_not_confirmed|collector_timeout|incomplete|page_chrome/i.test(
    String(envelope.error || envelope.capture_quality || envelope.capture_quality_detail || "")
  );
}

async function applyAnswerRescue(tab, spec, tool, envelope, beforeSnapshot, waited) {
  if (!shouldAttemptAnswerRescue(envelope, spec)) {
    return envelope;
  }
  const rescue = await answerRescue(tab, spec, tool, beforeSnapshot, waited).catch((error) => ({
    matched: false,
    reason: `answer_rescue_error:${String(error?.message || error)}`,
  }));
  if (!rescue?.matched) {
    if (envelope.status !== "ok") {
      envelope.capture_mode = envelope.capture_mode || "capture_failed";
      envelope.answer_confirmed = false;
      envelope.needs_human_review = true;
      envelope.candidate_reason = rescue?.reason || envelope.error || "answer_not_captured";
      envelope.diagnostic_text =
        envelope.diagnostic_text ||
        JSON.stringify({
          answer_rescue: rescue,
          before_snapshot: summarizeSnapshot(beforeSnapshot),
        }).slice(0, 2000);
    }
    return envelope;
  }
  envelope.status = "ok";
  envelope.send_confirmed = true;
  envelope.prompt_id_confirmed = true;
  envelope.response_started = true;
  envelope.response_completed = false;
  envelope.response_text = rescue.text;
  envelope.capture_quality = "weak";
  envelope.capture_quality_detail = "answer_rescue_candidate_after_selector_miss";
  envelope.capture_mode = "rescue_candidate";
  envelope.answer_confirmed = false;
  envelope.valid_answer = null;
  envelope.needs_human_review = true;
  envelope.needs_structure_review = true;
  envelope.candidate_score = rescue.score;
  envelope.candidate_reason = rescue.reason;
  envelope.error = "answer_rescue_candidate";
  envelope.diagnostic_text = JSON.stringify({
    answer_rescue: {
      selector: rescue.selector,
      score: rescue.score,
      reason: rescue.reason,
      text_hash: rescue.text_hash,
      candidate_count: rescue.candidate_count,
      ranked: rescue.ranked,
    },
    before_snapshot: summarizeSnapshot(beforeSnapshot),
    after_snapshot: summarizeSnapshot(rescue.afterSnapshot),
  }).slice(0, 2400);
  return envelope;
}

function summarizeSnapshot(snapshot) {
  if (!snapshot) {
    return null;
  }
  return {
    url: snapshot.url || "",
    prompt_seen: Boolean(snapshot.prompt_seen),
    user_prompt_seen: Boolean(snapshot.user_prompt_seen),
    user_message_count: snapshot.user_message_count || 0,
    ai_reply_count: snapshot.ai_reply_count || 0,
    body_tail_hash: snapshot.body_tail_hash || "",
    candidate_count: snapshot.candidate_count || 0,
  };
}

export function __testScoreAnswerRescueCandidate({ spec, item, tool = "千问", beforeSnapshot = null }) {
  return scoreAnswerRescueCandidate(spec, item, tool, beforeSnapshot);
}

export function __testSelectAnswerRescueCandidate({ spec, candidates, tool = "千问", beforeSnapshot = null }) {
  return selectAnswerRescueCandidate(spec, tool, beforeSnapshot, candidates);
}

async function captureTargetedReply(tab, spec, tool) {
  const fullText = await bodyText(tab, 120000).catch(() => "");
  const selectorMap = {
    "豆包": [
      '[data-testid*="message"]',
      '[class*="message"]',
      '[class*="Message"]',
      '[class*="markdown"]',
      '[class*="answer"]',
      '[class*="bot"]',
    ],
    "Gemini": [
      'model-response message-content',
      'model-response .markdown',
      'message-content .markdown',
      'message-content',
      '.model-response-text',
      '[class*="model-response"]',
      '[class*="response"]',
      '.markdown',
    ],
    "知乎直答": [
      '[data-testid="Block:zhida_answer_result_block"]',
      ".Render-markdown",
      '[data-testid*="answer"]',
      '[class*="Answer"]',
      '[class*="answer"]',
      '[class*="markdown"]',
      '[class*="RichText"]',
    ],
    "点点": [
      ".ai-message.ai-message-finished .markdown-block",
      ".ai-message.ai-message-finished p",
      ".ai-message.ai-message-finished",
    ],
  };
  const candidates = await captureCandidateTexts(tab, selectorMap[tool] || []);
  const ranked = candidates
    .map((item) => ({ ...item, score: replyScore(spec, item, tool) }))
    .sort((a, b) => b.score - a.score);
  if (ranked[0] && ranked[0].score > 0 && captureQualityGate(spec, ranked[0].text).ok) {
    return ranked[0].text
      .replace(/^Gemini said\s*/i, "")
      .replace(/Flash\s+Gemini is AI and can make mistakes\..*$/s, "")
      .trim();
  }
  if (tool === "Gemini") {
    const geminiIndex = fullText.lastIndexOf("Gemini said");
    if (geminiIndex >= 0) {
      const geminiTail = fullText.slice(geminiIndex + "Gemini said".length).replace(/Flash\s+Gemini is AI and can make mistakes\..*$/s, "").trim();
      if (captureQualityGate(spec, geminiTail).ok) {
        return geminiTail;
      }
    }
  }
  const tail = textAfterPrompt(fullText, spec.prompt_id);
  if (tail && captureQualityGate(spec, tail).ok) {
    return tail;
  }
  return ranked[0]?.text || tail || fullText;
}

async function waitForTargetedReply(tab, spec, tool, timeoutMs = DEFAULT_TIMEOUT) {
  const startedAt = Date.now();
  let promptSeen = false;
  let lastReply = "";
  let lastError = "reply_not_started";
  while (Date.now() - startedAt < timeoutMs) {
    const page = await bodyText(tab, 120000).catch(() => "");
    promptSeen = promptSeen || page.includes(spec.prompt_id);
    if (promptSeen) {
      const reply = await captureTargetedReply(tab, spec, tool);
      const gate = captureQualityGate(spec, reply);
      lastReply = reply;
      lastError = gate.error;
      if (gate.ok && !/正在|生成中|停止生成|Thinking|Generating|搜索中|思考中/.test(page.slice(-1500))) {
        return { seen: true, completed: true, text: reply, quality_error: "" };
      }
      if (gate.ok) {
        lastError = "";
      }
    }
    await tab.playwright.waitForTimeout(4000);
  }
  return { seen: promptSeen, completed: false, text: lastReply, quality_error: lastError };
}

function envelopeFromTargetedWait(spec, waited, submittedAt, captureQuality) {
  const responseText = waited.text || "";
  const hasReply = Boolean(waited.seen && responseText.trim());
  const weakReason = hasReply ? String(waited.quality_error || "") : "";
  const quality = weakReason ? "weak" : inferTargetedCaptureQuality(responseText, waited.completed);
  return {
    submitted_at: submittedAt,
    status: hasReply ? "ok" : "error",
    send_confirmed: Boolean(waited.seen),
    prompt_id_confirmed: Boolean(waited.seen),
    response_started: responseText.trim().length > 0,
    response_completed: Boolean(waited.completed),
    response_text: hasReply ? responseText : "",
    source_url: "",
    capture_quality: hasReply ? quality : "answer_not_captured",
    capture_quality_detail: captureQuality,
    needs_structure_review: hasReply,
    error: hasReply ? weakReason : (waited.quality_error || (waited.seen ? "answer_not_captured" : "user_message_not_confirmed")),
    diagnostic_text: hasReply && weakReason ? responseText.slice(0, 2000) : "",
  };
}

function inferTargetedCaptureQuality(responseText, completed) {
  const text = String(responseText || "");
  if (completed && (hasRealUrl(text) || hasStructuredEvidenceSignal(text) || text.length >= 800)) {
    return "strong";
  }
  return "normal";
}

async function addCurrentUrl(tab, envelope) {
  envelope.source_url = await tab.url().catch(() => "");
  return envelope;
}

async function ensureToolTab(ctx, tool, url) {
  let tab = ctx.tabsByTool[tool];
  if (!tab) {
    tab = await ctx.iab.tabs.new();
    ctx.tabsByTool[tool] = tab;
  }
  const currentUrl = await tab.url().catch(() => "");
  const baseUrl = url.split("?")[0];
  if (!currentUrl || !currentUrl.startsWith(baseUrl)) {
    await tab.goto(url);
    await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 45000 }).catch(() => {});
    await tab.playwright.waitForTimeout(3000);
  }
  return tab;
}

async function findGenericChatInput(tab, tool) {
  const picked = await tab.playwright.evaluate((toolName) => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const selector = [
      "textarea",
      "[contenteditable='true'][role='textbox']",
      "div[role='textbox'][contenteditable='true']",
      "[contenteditable='true']",
    ].join(",");
    const seen = new Set();
    const candidates = Array.from(document.querySelectorAll(selector))
      .filter((el) => {
        if (seen.has(el)) {
          return false;
        }
        seen.add(el);
        return true;
      })
      .map((el, index) => {
        const r = el.getBoundingClientRect();
        const text = (el.value || el.innerText || el.textContent || "").trim();
        const placeholder = el.getAttribute("placeholder") || el.getAttribute("aria-label") || "";
        const disabled = Boolean(el.disabled) || el.getAttribute("aria-disabled") === "true";
        const readonly = Boolean(el.readOnly) || el.getAttribute("readonly") != null;
        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute("role") || "";
        const type = tag === "textarea" ? "textarea" : "contenteditable";
        const area = Math.round(r.width * r.height);
        const promptLike = /输入|发消息|询问|问点|Message|Ask|send|prompt|Grok|Yuanbao|元宝|豆包|千问|Qianwen/i.test(placeholder);
        const score =
          (visible(el) ? 1000 : 0) +
          (!disabled && !readonly ? 500 : 0) +
          (type === "textarea" ? 80 : 40) +
          (role === "textbox" ? 50 : 0) +
          (promptLike ? 60 : 0) +
          Math.min(120, Math.floor(area / 1200)) +
          Math.min(200, Math.floor(Math.max(0, r.y) / 3)) -
          Math.min(300, text.length);
        return {
          index,
          tag,
          type,
          role,
          placeholder,
          visible: visible(el),
          disabled,
          readonly,
          area,
          rect: { x: r.x, y: r.y, width: r.width, height: r.height },
          score,
          toolName,
        };
      })
      .filter((item) => item.visible && !item.disabled && !item.readonly && item.area > 800);
    candidates.sort((a, b) => b.score - a.score);
    return { picked: candidates[0] || null, diagnostics: candidates.slice(0, 8) };
  }, tool, { timeoutMs: 15000 });
  if (!picked?.picked) {
    throw new Error(`generic_input_not_found:${tool}:${JSON.stringify(picked?.diagnostics || []).slice(0, 1200)}`);
  }
  const all = tab.playwright.locator("textarea,[contenteditable='true'][role='textbox'],div[role='textbox'][contenteditable='true'],[contenteditable='true']");
  return { locator: all.nth(picked.picked.index), type: picked.picked.type, diagnostics: picked.diagnostics };
}

async function pasteIntoGenericInput(tab, inputInfo, text, promptId, tool) {
  if (inputInfo.type === "textarea") {
    await clearAndPaste(tab, inputInfo.locator, text);
  } else {
    await clearAndPasteContentEditable(tab, inputInfo.locator, text);
  }
  if (await promptVisibleInInputOrPage(tab, inputInfo.locator, promptId, 12000)) {
    return;
  }
  await inputInfo.locator.click({ timeoutMs: 10000 }).catch(() => {});
  await inputInfo.locator.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
  await inputInfo.locator.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
  await inputInfo.locator.type(text, { timeoutMs: 90000 }).catch(() => {});
  if (await promptVisibleInInputOrPage(tab, inputInfo.locator, promptId, 15000)) {
    return;
  }
  throw new Error(`${tool}_prompt_id_not_in_generic_input`);
}

async function promptVisibleInInputOrPage(tab, locator, promptId, timeoutMs = 12000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const draft = await valueOf(locator).catch(() => "");
    if (draft.includes(promptId)) {
      return true;
    }
    const activeText = await tab.playwright.evaluate(() => {
      const active = document.activeElement;
      return active ? (active.value || active.innerText || active.textContent || "") : "";
    }, null, { timeoutMs: 5000 }).catch(() => "");
    if (activeText.includes(promptId)) {
      return true;
    }
    const pageText = await bodyText(tab, 20000).catch(() => "");
    if (pageText.includes(promptId)) {
      return true;
    }
    await tab.playwright.waitForTimeout(1000);
  }
  return false;
}

async function sendGenericChatPrompt(tab, inputInfo, tool) {
  const sendIndex = await tab.playwright.evaluate(() => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const controls = Array.from(document.querySelectorAll("button,[role='button'],svg,[aria-label]"))
      .map((el, index) => {
        const r = el.getBoundingClientRect();
        const text = [
          el.innerText || "",
          el.textContent || "",
          el.getAttribute("aria-label") || "",
          el.getAttribute("title") || "",
          el.getAttribute("class") || "",
        ].join(" ");
        const disabled = Boolean(el.disabled) || el.getAttribute("aria-disabled") === "true";
        const sendLike = /发送|提交|Send|send|submit|arrow|paper|飞机|↑|➤/i.test(text);
        const bottom = r.y > window.innerHeight * 0.45;
        const right = r.x > window.innerWidth * 0.45;
        const area = Math.round(r.width * r.height);
        const score =
          (visible(el) ? 1000 : 0) +
          (!disabled ? 300 : 0) +
          (sendLike ? 400 : 0) +
          (bottom ? 120 : 0) +
          (right ? 80 : 0) +
          Math.min(100, area);
        return { index, score, visible: visible(el), disabled, sendLike, rect: { x: r.x, y: r.y, width: r.width, height: r.height }, text: text.slice(0, 120) };
      })
      .filter((item) => item.visible && !item.disabled && item.sendLike && item.rect.width > 4 && item.rect.height > 4)
      .sort((a, b) => b.score - a.score);
    return controls[0]?.index ?? -1;
  }, null, { timeoutMs: 15000 }).catch(() => -1);
  if (sendIndex >= 0) {
    await tab.playwright.locator("button,[role='button'],svg,[aria-label]").nth(sendIndex).click({ timeoutMs: 10000 });
    return "generic_send_button";
  }
  await inputInfo.locator.press("Enter", { timeoutMs: 10000 });
  return `${tool}_enter_send`;
}

async function submitGenericChatTool(ctx, spec, { tool, url, captureQuality, timeoutMs = DEFAULT_TIMEOUT }) {
  const tab = await ensureToolTab(ctx, tool, url);
  const inputInfo = await findGenericChatInput(tab, tool);
  await pasteIntoGenericInput(tab, inputInfo, spec.text, spec.prompt_id, tool);
  const beforeSnapshot = await capturePageSnapshot(tab, spec, tool).catch(() => null);
  const sendMethod = await sendGenericChatPrompt(tab, inputInfo, tool);
  const submittedAt = new Date().toISOString();
  const waited = await waitForTargetedReply(tab, spec, tool, timeoutMs);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, captureQuality);
  envelope.send_method = sendMethod;
  envelope.diagnostic_text = envelope.status === "ok" ? "" : JSON.stringify(inputInfo.diagnostics || []).slice(0, 2000);
  await applyAnswerRescue(tab, spec, tool, envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

function extractYuanbaoReplyAfterPrompt(pageText, spec) {
  const text = String(pageText || "");
  const best = bestPromptTailCandidate(text, spec, "元宝");
  if (best) {
    return best;
  }
  const promptIndex = text.lastIndexOf(spec.prompt_id);
  if (promptIndex < 0) {
    return "";
  }
  let tail = text.slice(promptIndex + spec.prompt_id.length);
  const firstItem = tail.search(/(?:^|\n)\s*(?:1[\.、]|一[、.．])/);
  if (firstItem >= 0) {
    tail = tail.slice(firstItem).trim();
  } else {
    const jsonStart = tail.search(/\{\s*"?(?:evidence|items|results|game_name)/i);
    if (jsonStart >= 0) {
      tail = tail.slice(jsonStart).trim();
    }
  }
  tail = tail.replace(/\n源\n[\s\S]*$/m, "").trim();
  if (looksLikePromptInstruction(tail) && !hasGameIntelSignal(tail)) {
    return "";
  }
  return tail;
}

async function waitForYuanbaoReply(tab, spec, timeoutMs = DEFAULT_TIMEOUT) {
  const startedAt = Date.now();
  let promptSeen = false;
  let lastReply = "";
  while (Date.now() - startedAt < timeoutMs) {
    const page = await bodyText(tab, 120000).catch(() => "");
    promptSeen = promptSeen || page.includes(spec.prompt_id);
    const reply = extractYuanbaoReplyAfterPrompt(page, spec);
    if (reply) {
      lastReply = reply;
      const enough = reply.length > 220 && hasGameIntelSignal(reply);
      const stillGenerating = /正在|生成中|停止生成|搜索中|思考中/.test(page.slice(-1500));
      if (enough && !stillGenerating) {
        return { seen: true, completed: true, text: reply, quality_error: "" };
      }
    }
    await tab.playwright.waitForTimeout(3000);
  }
  return {
    seen: promptSeen,
    completed: false,
    text: lastReply,
    quality_error: lastReply ? "yuanbao_reply_incomplete" : "reply_not_started",
  };
}

function extractGrokReplyAfterPrompt(pageText, spec) {
  const text = String(pageText || "");
  const best = bestPromptTailCandidate(text, spec, "Grok");
  if (best) {
    return best;
  }
  const promptIndex = text.indexOf(spec.prompt_id);
  if (promptIndex < 0) {
    return "";
  }
  let tail = text.slice(promptIndex + spec.prompt_id.length);
  const answerStart = tail.search(/(?:^|\n)\s*(?:思考了\s*\d+s\s*\n)?(?:游戏名|1[\.、]|一[、.．])/);
  if (answerStart >= 0) {
    tail = tail.slice(answerStart).trim();
  }
  const nextPrompt = tail.indexOf("AUTOMATION_MARKER");
  if (nextPrompt > 200) {
    tail = tail.slice(0, nextPrompt).trim();
  }
  tail = tail.replace(/\n(?:Analyze|Investigate|Verify|Search|Create)\b[\s\S]*$/m, "").trim();
  if (looksLikePromptInstruction(tail) && !hasGameIntelSignal(tail)) {
    return "";
  }
  return tail;
}

async function waitForGrokReply(tab, spec, timeoutMs = DEFAULT_TIMEOUT) {
  const startedAt = Date.now();
  let promptSeen = false;
  let lastReply = "";
  while (Date.now() - startedAt < timeoutMs) {
    const page = await bodyText(tab, 120000).catch(() => "");
    promptSeen = promptSeen || page.includes(spec.prompt_id);
    const reply = extractGrokReplyAfterPrompt(page, spec);
    if (reply) {
      lastReply = reply;
      const enough = reply.length > 220 && hasGameIntelSignal(reply);
      const stillGenerating = /Thinking|Generating|Stop generating|搜索中|思考中/.test(page.slice(-1500));
      if (enough && !stillGenerating) {
        return { seen: true, completed: true, text: reply, quality_error: "" };
      }
    }
    await tab.playwright.waitForTimeout(3000);
  }
  return {
    seen: promptSeen,
    completed: false,
    text: lastReply,
    quality_error: lastReply ? "grok_reply_incomplete" : "reply_not_started",
  };
}

export async function submitDoubao(ctx, spec) {
  const tab = await ensureToolTab(ctx, "豆包", "https://www.doubao.com/chat/?channel=browser_landing_page");
  let inputInfo;
  try {
    inputInfo = await findGenericChatInput(tab, "豆包");
  } catch (error) {
    const diagnostics = await visiblePageDiagnostics(tab).catch((diagError) => ({ error: String(diagError?.message || diagError) }));
    throw new Error(`doubao_input_not_found:${JSON.stringify({
      reason: String(error?.message || error),
      url: diagnostics.url || "",
      title: diagnostics.title || "",
      visible_textarea_count: diagnostics.textareas?.length || 0,
      contenteditable_count: diagnostics.editors?.length || 0,
      diagnostics,
    }).slice(0, 2200)}`);
  }
  await pasteIntoGenericInput(tab, inputInfo, spec.text, spec.prompt_id, "豆包");
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "豆包").catch(() => null);
  await inputInfo.locator.press("Enter", { timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForTargetedReply(tab, spec, "豆包", DEFAULT_TIMEOUT);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "doubao_targeted_reply_after_current_prompt");
  await applyAnswerRescue(tab, spec, "豆包", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

export async function submitQianwen(ctx, spec) {
  const tab = await ensureToolTab(ctx, "千问", "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5");
  let inputInfo;
  try {
    inputInfo = await findGenericChatInput(tab, "千问");
    await pasteIntoGenericInput(tab, inputInfo, spec.text, spec.prompt_id, "千问");
  } catch (error) {
    const diagnostics = await visiblePageDiagnostics(tab).catch((diagError) => ({ error: String(diagError?.message || diagError) }));
    throw new Error(`qianwen_prompt_paste_failed:${JSON.stringify({
      reason: String(error?.message || error),
      url: diagnostics.url || "",
      title: diagnostics.title || "",
      visible_textarea_count: diagnostics.textareas?.length || 0,
      contenteditable_count: diagnostics.editors?.length || 0,
      diagnostics,
    }).slice(0, 2200)}`);
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "千问").catch(() => null);
  await inputInfo.locator.press("Enter", { timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForStableCurrentPrompt(tab, spec.prompt_id, DEFAULT_TIMEOUT);
  const fullText = await bodyText(tab, 100000).catch(() => waited.text || "");
  const envelope = {
    ...envelopeFromWait(spec, tab, { ...waited, text: fullText }, submittedAt, "qianwen_full_visible_page_after_prompt_confirmed"),
    response_completed: waited.completed || fullText.includes(spec.prompt_id),
  };
  await applyAnswerRescue(tab, spec, "千问", envelope, beforeSnapshot, { ...waited, text: fullText });
  return addCurrentUrl(tab, envelope);
}

export async function submitWenxin(ctx, spec) {
  const tab = await ensureToolTab(ctx, "文心一言", "https://wenxin.baidu.com/");
  await tab.goto("https://wenxin.baidu.com/");
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 20000 }).catch(() => {});
  const newChat = tab.playwright.locator('.new-dialog-container-button:has-text("开启新对话")').filter({ visible: true });
  if (await newChat.count().catch(() => 0) === 1) {
    await newChat.click({ timeoutMs: 10000 }).catch(() => {});
  }
  const input = tab.playwright.locator("textarea#chat-textarea.ci-textarea");
  await input.waitFor({ state: "visible", timeoutMs: 45000 });
  if (await visibleCount(input) !== 1) {
    throw new Error(`wenxin_visible_input_not_unique:${await visibleCount(input)}`);
  }
  await clearAndPaste(tab, input, spec.text);
  const draft = await valueOf(input);
  if (!draft.includes(spec.prompt_id)) {
    throw new Error("wenxin_prompt_id_not_in_textarea_value");
  }
  const send = tab.playwright.locator("#ci-submit-button-ai.ci-submit-button-ai-active").filter({ visible: true });
  const sendCount = await send.count();
  if (sendCount !== 1) {
    throw new Error(`wenxin_send_control_not_unique_or_inactive:${sendCount}`);
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "文心一言").catch(() => null);
  await send.click({ timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForStableCurrentPrompt(tab, spec.prompt_id, DEFAULT_TIMEOUT);
  const envelope = envelopeFromWait(spec, tab, waited, submittedAt, "wenxin_safe_prompt_unique_textarea");
  await applyAnswerRescue(tab, spec, "文心一言", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

async function findGeminiInput(tab) {
  const selector = [
    'div.ql-editor[contenteditable="true"][role="textbox"]',
    'div.ql-editor[contenteditable="true"]',
    '[contenteditable="true"][role="textbox"]',
    'div[role="textbox"]',
    '[contenteditable="true"]',
    "textarea",
  ].join(",");
  const picked = await tab.playwright.evaluate((allSelector) => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const all = Array.from(document.querySelectorAll(allSelector));
    const candidates = all
      .map((el, index) => {
        const r = el.getBoundingClientRect();
        const cls = String(el.getAttribute("class") || "");
        const role = el.getAttribute("role") || "";
        const contenteditable = el.getAttribute("contenteditable") === "true";
        const text = (el.value || el.innerText || el.textContent || "").trim();
        const area = Math.round(r.width * r.height);
        const priority =
          (/ql-editor/.test(cls) ? 500 : 0) +
          (contenteditable ? 180 : 0) +
          (role === "textbox" ? 160 : 0) +
          (el.tagName.toLowerCase() === "textarea" ? 80 : 0) +
          Math.min(180, Math.floor(area / 1200)) +
          Math.min(140, Math.floor(Math.max(0, r.y) / 4)) -
          Math.min(250, text.length);
        return {
          index,
          tag: el.tagName.toLowerCase(),
          cls: cls.slice(0, 120),
          role,
          contenteditable,
          visible: visible(el),
          disabled: Boolean(el.disabled) || el.getAttribute("aria-disabled") === "true",
          area,
          text: text.slice(0, 80),
          rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
          priority,
        };
      })
      .filter((item) => item.visible && !item.disabled && item.area > 800);
    candidates.sort((a, b) => b.priority - a.priority);
    return {
      candidates,
      picked: candidates[0] || null,
      pickedIndex: Number.isFinite(candidates[0]?.index) ? candidates[0].index : -1,
      ambiguous: candidates.length > 1 && candidates[0]?.priority === candidates[1]?.priority,
    };
  }, selector, { timeoutMs: 15000 });
  if (!picked?.candidates?.length) {
    const diagnostics = await visiblePageDiagnostics(tab).catch((error) => ({ error: String(error?.message || error) }));
    throw new Error(`gemini_input_not_found:${JSON.stringify(diagnostics).slice(0, 2200)}`);
  }
  if (picked.ambiguous) {
    throw new Error(`gemini_input_ambiguous:${JSON.stringify(picked.candidates.slice(0, 6)).slice(0, 1800)}`);
  }
  if (!Number.isFinite(picked.pickedIndex) || picked.pickedIndex < 0) {
    throw new Error(`gemini_input_index_invalid:${JSON.stringify(picked.candidates.slice(0, 6)).slice(0, 1800)}`);
  }
  return {
    locator: tab.playwright.locator(selector).nth(picked.pickedIndex),
    type: picked.picked.tag === "textarea" ? "textarea" : "contenteditable",
    diagnostics: picked.candidates.slice(0, 6),
  };
}

export async function submitGemini(ctx, spec) {
  const tab = await ensureToolTab(ctx, "Gemini", "https://gemini.google.com/app");
  const inputInfo = await findGeminiInput(tab);
  await pasteIntoGenericInput(tab, inputInfo, spec.text, spec.prompt_id, "Gemini");
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "Gemini").catch(() => null);
  await inputInfo.locator.press("Enter", { timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForTargetedReply(tab, spec, "Gemini", DEFAULT_TIMEOUT);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "gemini_targeted_model_reply");
  await applyAnswerRescue(tab, spec, "Gemini", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

async function ensureDianDianAiChatInput(tab) {
  await tab.goto("https://www.xiaohongshu.com/ai_chat");
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 20000 }).catch(() => {});
  await tab.playwright.waitForTimeout(4000);
  let input = await findDianDianActiveInput(tab);
  if (input) {
    return input;
  }

  const aiChatLink = tab.playwright.locator('a[href*="/ai_chat"], a[href*="ai_chat"]').filter({ visible: true });
  const linkCount = await aiChatLink.count().catch(() => 0);
  if (linkCount === 1) {
    await aiChatLink.click({ timeoutMs: 10000 }).catch(() => {});
    await tab.playwright.waitForTimeout(4000);
  } else {
    const entryIndex = await tab.playwright.evaluate(() => {
      const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
      return Array.from(document.querySelectorAll("a,button,[role='button']"))
        .map((el, index) => ({ el, index, text: (el.innerText || el.textContent || "").trim() }))
        .filter((item) => visible(item.el) && /点点|AI\s*Chat|ai_chat/i.test(item.text))
        .map((item) => item.index)[0] ?? -1;
    }, null, { timeoutMs: 10000 }).catch(() => -1);
    if (entryIndex >= 0) {
      await tab.playwright.locator("a,button,[role='button']").nth(entryIndex).click({ timeoutMs: 10000 }).catch(() => {});
      await tab.playwright.waitForTimeout(5000);
    }
  }

  input = await findDianDianActiveInput(tab);
  if (input) {
    return input;
  }
  const diagnostics = await visiblePageDiagnostics(tab).catch((error) => ({ error: String(error?.message || error) }));
  throw new Error(`diandian_ai_chat_entry_not_reached:${JSON.stringify(diagnostics).slice(0, 1800)}`);
}

async function findDianDianActiveInput(tab) {
  const inputIndex = await tab.playwright.evaluate(() => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const inputs = Array.from(document.querySelectorAll('textarea[name="aiSearchTextarea"]'));
    const candidates = inputs
      .map((el, index) => {
        const r = el.getBoundingClientRect();
        const parent = el.closest(".ai-chat-welcome__input, .textarea-container.ai-chat-input-box, .wendian-wrapper");
        return {
          index,
          visible: visible(el),
          tabIndex: el.tabIndex,
          ariaHidden: el.getAttribute("aria-hidden") === "true",
          disabled: Boolean(el.disabled),
          activeChain: Boolean(parent),
          area: Math.round(r.width * r.height),
          placeholder: el.getAttribute("placeholder") || "",
        };
      })
      .filter((item) => item.visible && !item.disabled && !item.ariaHidden && item.area > 0);
    candidates.sort((a, b) => {
      const score = (item) =>
        (item.tabIndex === 0 ? 100 : 0) +
        (item.activeChain ? 40 : 0) +
        (/搜索或者输入任何问题|生活中|推荐|问题/.test(item.placeholder) ? 5 : 0) +
        Math.min(20, Math.floor(item.area / 10000));
      return score(b) - score(a);
    });
    return candidates[0]?.index ?? -1;
  }, null, { timeoutMs: 10000 }).catch(() => -1);
  if (inputIndex < 0) {
    return null;
  }
  return tab.playwright.locator('textarea[name="aiSearchTextarea"]').nth(inputIndex);
}

export async function submitDianDian(ctx, spec) {
  const tab = await ensureToolTab(ctx, "点点", "https://www.xiaohongshu.com/ai_chat");
  const input = await ensureDianDianAiChatInput(tab);
  const inputCount = await input.count();
  if (inputCount !== 1) {
    throw new Error(`diandian_visible_input_not_unique:${inputCount}`);
  }
  await clearAndPaste(tab, input, spec.text);
  const draft = await valueOf(input);
  if (!draft.includes(spec.prompt_id)) {
    throw new Error("diandian_prompt_id_not_in_textarea_value");
  }
  const send = tab.playwright.locator(".ai-chat-welcome__input .submit-button-wrapper, .textarea-container.ai-chat-input-box .submit-button-wrapper").filter({ visible: true });
  const sendCount = await send.count();
  if (sendCount < 1) {
    throw new Error(`diandian_send_control_not_found:${sendCount}`);
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "点点").catch(() => null);
  await send.first().click({ timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForTargetedReply(tab, spec, "点点", DEFAULT_TIMEOUT);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "diandian_targeted_finished_ai_message");
  await applyAnswerRescue(tab, spec, "点点", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

async function findZhidaEditor(tab, timeoutMs = 45000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const editorIndex = await tab.playwright.evaluate(() => {
      const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
      const candidates = Array.from(document.querySelectorAll('[contenteditable="true"][role="textbox"], .public-DraftEditor-content[contenteditable="true"]'))
        .map((el, index) => {
          const r = el.getBoundingClientRect();
          return {
            index,
            visible: visible(el),
            text: (el.innerText || el.textContent || "").trim(),
            area: Math.round(r.width * r.height),
            rect: { x: r.x, y: r.y, width: r.width, height: r.height },
          };
        })
        .filter((item) => item.visible && item.area > 0 && item.rect.y > 160);
      candidates.sort((a, b) => b.area - a.area);
      return candidates[0]?.index ?? -1;
    }, null, { timeoutMs: 10000 }).catch(() => -1);
    if (editorIndex >= 0) {
      return tab.playwright.locator('[contenteditable="true"][role="textbox"], .public-DraftEditor-content[contenteditable="true"]').nth(editorIndex);
    }
    await tab.playwright.waitForTimeout(2000);
  }
  throw new Error("zhida_visible_editor_not_found");
}

export async function submitZhida(ctx, spec) {
  const tab = await ensureToolTab(ctx, "知乎直答", "https://zhida.zhihu.com/");
  await tab.goto("https://zhida.zhihu.com/");
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 20000 }).catch(() => {});
  await tab.playwright.waitForTimeout(2000);
  const editor = await findZhidaEditor(tab);
  await clearAndPasteContentEditable(tab, editor, spec.text);
  const draft = await valueOf(editor);
  if (!draft.includes(spec.prompt_id)) {
    throw new Error("zhida_prompt_id_not_in_editor_value");
  }
  const beforeUrl = await tab.url();
  const sendIndex = await tab.playwright.evaluate(() => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const rect = (el) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    };
    return Array.from(document.querySelectorAll("div.r-1loqt21.r-1otgn73"))
      .map((el, index) => ({ index, el, rect: rect(el) }))
      .filter((item) => visible(item.el) && item.rect.y > 240 && item.rect.y < 430)
      .sort((a, b) => b.rect.x - a.rect.x)[0]?.index ?? -1;
  });
  if (sendIndex < 0) {
    throw new Error("zhida_send_control_not_found");
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "知乎直答").catch(() => null);
  await tab.playwright.locator("div.r-1loqt21.r-1otgn73").nth(sendIndex).click({ timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const startedAt = Date.now();
  let routeChanged = false;
  while (Date.now() - startedAt < 120000) {
    const currentUrl = await tab.url().catch(() => "");
    if (currentUrl !== beforeUrl && /\/search\//.test(currentUrl)) {
      routeChanged = true;
      break;
    }
    await tab.playwright.waitForTimeout(3000);
  }
  if (!routeChanged) {
    const envelope = {
      submitted_at: submittedAt,
      status: "error",
      send_confirmed: false,
      prompt_id_confirmed: false,
      response_started: false,
      response_completed: false,
      response_text: "",
      capture_quality: "zhida_route_not_confirmed",
      error: "zhida_new_search_route_not_confirmed",
      diagnostic_text: JSON.stringify(await visiblePageDiagnostics(tab).catch((error) => ({ error: String(error?.message || error) }))),
    };
    await applyAnswerRescue(tab, spec, "知乎直答", envelope, beforeSnapshot, { seen: false, completed: false, text: "", quality_error: envelope.error });
    return addCurrentUrl(tab, envelope);
  }
  const waited = await waitForTargetedReply(tab, spec, "知乎直答", DEFAULT_TIMEOUT);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "zhida_new_search_targeted_answer");
  if (envelope.status === "ok" && looksLikeOffTopicAnswer(envelope.response_text, spec)) {
    envelope.capture_quality = "weak";
    envelope.capture_quality_detail = "zhida_new_search_targeted_answer";
    envelope.needs_structure_review = true;
    envelope.error = "zhida_answer_drift_off_topic";
    envelope.diagnostic_text = envelope.response_text.slice(0, 2000);
  }
  await applyAnswerRescue(tab, spec, "知乎直答", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

export async function submitYuanbao(ctx, spec) {
  const tab = await ensureToolTab(ctx, "元宝", "https://yuanbao.tencent.com/chat/naQivTmsDa");
  const editor = tab.playwright.locator('.ql-editor[contenteditable="true"]').filter({ visible: true });
  const editorCount = await editor.count();
  if (editorCount !== 1) {
    throw new Error(`yuanbao_editor_not_unique:${editorCount}`);
  }
  await editor.click({ timeoutMs: 10000 });
  await editor.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
  await editor.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
  await editor.fill(spec.text, { timeoutMs: 20000 }).catch(async () => {
    await tab.clipboard.writeText(spec.text);
    await editor.click({ timeoutMs: 10000 });
    await editor.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
    await editor.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
    await editor.press("Control+V", { timeoutMs: 20000 });
  });
  await tab.playwright.waitForTimeout(1500);
  const startedAt = Date.now();
  let promptConfirmed = false;
  while (Date.now() - startedAt < 30000) {
    const draft = await valueOf(editor).catch(() => "");
    const page = await bodyText(tab, 50000).catch(() => "");
    if (draft.includes(spec.prompt_id) || page.includes(spec.prompt_id)) {
      promptConfirmed = true;
      break;
    }
    await tab.playwright.waitForTimeout(1000);
  }
  const sendIndex = await tab.playwright.evaluate(() => {
    const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const items = Array.from(document.querySelectorAll(".hyc-common-icon.icon-send, .icon-send"))
      .map((el, index) => {
        const r = el.getBoundingClientRect();
        return { index, visible: visible(el), rect: { x: r.x, y: r.y, width: r.width, height: r.height } };
      })
      .filter((item) => item.visible && item.rect.width > 4 && item.rect.height > 4)
      .sort((a, b) => (b.rect.y - a.rect.y) || (b.rect.x - a.rect.x));
    return items[0]?.index ?? -1;
  }, null, { timeoutMs: 10000 });
  if (sendIndex < 0) {
    throw new Error(`yuanbao_send_control_not_found:${JSON.stringify(await visiblePageDiagnostics(tab).catch((error) => ({ error: String(error?.message || error) }))).slice(0, 1600)}`);
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "元宝").catch(() => null);
  await tab.playwright.locator(".hyc-common-icon.icon-send, .icon-send").nth(sendIndex).click({ timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForYuanbaoReply(tab, spec, DEFAULT_TIMEOUT);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "yuanbao_targeted_current_reply");
  if (!promptConfirmed && envelope.status !== "ok") {
    envelope.capture_quality = "yuanbao_prompt_send_unconfirmed";
    envelope.error = envelope.error || "yuanbao_prompt_id_not_confirmed_before_send";
  }
  await applyAnswerRescue(tab, spec, "元宝", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

export async function submitGrok(ctx, spec) {
  const tab = await ensureToolTab(ctx, "Grok", "https://grok.com/");
  const input = tab.playwright.locator('[data-testid="chat-input"] [contenteditable="true"], div[aria-label="Ask Grok anything"][contenteditable="true"]').filter({ visible: true });
  const inputCount = await input.count();
  if (inputCount < 1) {
    throw new Error(`grok_input_not_found:${JSON.stringify(await visiblePageDiagnostics(tab).catch((error) => ({ error: String(error?.message || error) }))).slice(0, 1600)}`);
  }
  const target = inputCount === 1 ? input : input.last();
  await clearAndPasteContentEditable(tab, target, spec.text);
  await tab.playwright.waitForTimeout(1500);
  const send = tab.playwright.locator('[data-testid="chat-submit"], button[aria-label="提交"], button[aria-label="Submit"]').filter({ visible: true });
  const sendCount = await send.count();
  if (sendCount < 1) {
    throw new Error(`grok_send_control_not_found:${sendCount}`);
  }
  const beforeSnapshot = await capturePageSnapshot(tab, spec, "Grok").catch(() => null);
  await send.last().click({ timeoutMs: 10000 });
  const submittedAt = new Date().toISOString();
  const waited = await waitForGrokReply(tab, spec, spec.short_fallback ? DEFAULT_TIMEOUT : 120000);
  const envelope = envelopeFromTargetedWait(spec, waited, submittedAt, "grok_targeted_current_reply");
  await applyAnswerRescue(tab, spec, "Grok", envelope, beforeSnapshot, waited);
  return addCurrentUrl(tab, envelope);
}

export async function submitByTool(ctx, spec) {
  const handlers = {
    "元宝": submitYuanbao,
    "豆包": submitDoubao,
    "文心一言": submitWenxin,
    "千问": submitQianwen,
    "点点": submitDianDian,
    "知乎直答": submitZhida,
    Gemini: submitGemini,
    Grok: submitGrok,
  };
  const handler = handlers[spec.ai_tool];
  if (!handler) {
    throw new Error(`no_v044_handler:${spec.ai_tool}`);
  }
  const first = await handler(ctx, spec);
  const firstProblem = String(first.error || first.capture_quality || first.capture_quality_detail || "");
  const retryable =
    !spec.short_fallback &&
    /(answer_not_captured|answer_drift|prompt_echo|route_not_confirmed|user_message_not_confirmed|reply_not_started)/.test(firstProblem) &&
    (first.status !== "ok" || first.capture_quality === "weak");
  if (!retryable) {
    return first;
  }
  const fallback = promptSpec(ctx, spec.original_prompt_id || spec.prompt_id, { fallback: true });
  if (!fallback?.text || fallback.prompt_id === spec.prompt_id) {
    first.fallback_recommended = true;
    return first;
  }
  const second = await handler(ctx, fallback);
  second.prompt_id = fallback.prompt_id;
  second.original_prompt_id = fallback.original_prompt_id;
  second.ai_tool = fallback.ai_tool;
  second.short_fallback = true;
  second.original_failed_prompt_id = spec.prompt_id;
  second.used_automatic_fallback = true;
  second.primary_error = first.error || first.capture_quality || "";
  return second;
}
