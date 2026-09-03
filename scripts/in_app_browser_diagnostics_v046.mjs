// Lightweight diagnostics for Codex in-app browser Web AI collectors.
// This module sends tiny test prompts and records safe DOM/route/capture facts.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

function safeStamp() {
  return new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
}

async function probePage(tab, tool) {
  const url = await tab.url().catch(() => "");
  const title = await tab.title().catch(() => "");
  const probe = await tab.playwright.evaluate(() => {
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
        text: (el.innerText || el.textContent || "").trim().slice(0, 100),
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      };
    };
    const body = document.body?.innerText || "";
    return {
      textareas: Array.from(document.querySelectorAll("textarea")).filter(visible).map(brief),
      inputs: Array.from(document.querySelectorAll("input")).filter(visible).slice(0, 20).map(brief),
      editors: Array.from(document.querySelectorAll('[contenteditable="true"], [role="textbox"]')).filter(visible).map(brief),
      buttons: Array.from(document.querySelectorAll('button,[role="button"],.submit-button-wrapper,div.r-1loqt21.r-1otgn73')).filter(visible).slice(0, 30).map(brief),
      hasLoginHints: /登录|登陆|Sign in|Log in|验证码|captcha|403|Forbidden/.test(body),
      bodyTail: body.slice(-1200),
    };
  }, null, { timeoutMs: 15000 }).catch((error) => ({ error: String(error?.message || error) }));
  return { tool, url, title, probe };
}

async function waitForMarker(tab, promptId, expected, beforeUrl, beforeLength) {
  let text = "";
  let finalUrl = "";
  for (let index = 0; index < 8; index += 1) {
    await tab.playwright.waitForTimeout(3000);
    finalUrl = await tab.url().catch(() => "");
    text = await tab.playwright.evaluate(() => (document.body?.innerText || "").slice(-12000), null, { timeoutMs: 10000 }).catch(() => "");
    if (text.includes(expected)) {
      break;
    }
  }
  return {
    finalUrl,
    routeChanged: finalUrl !== beforeUrl,
    containsPrompt: text.includes(promptId),
    containsExpected: text.includes(expected),
    promptMatches: text.split(promptId).length - 1,
    expectedMatches: text.split(expected).length - 1,
    bodyLenDelta: text.length - beforeLength,
    tailExcerpt: text.slice(-1200),
  };
}

async function fillTextarea(tab, locator, prompt, promptId) {
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(`textarea_not_unique:${count}`);
  }
  await locator.fill(prompt, { timeoutMs: 15000 });
  const draft = await locator.evaluate((el) => el.value || el.innerText || el.textContent || "", null, { timeoutMs: 5000 });
  if (!draft.includes(promptId)) {
    throw new Error("prompt_id_not_in_textarea");
  }
}

async function pasteEditor(tab, locator, prompt, promptId) {
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(`editor_not_unique:${count}`);
  }
  await tab.clipboard.writeText(prompt);
  await locator.click({ timeoutMs: 10000 });
  await locator.press("Control+A", { timeoutMs: 5000 }).catch(() => {});
  await locator.press("Backspace", { timeoutMs: 5000 }).catch(() => {});
  await locator.press("Control+V", { timeoutMs: 15000 });
  const draft = await locator.evaluate((el) => el.innerText || el.textContent || "", null, { timeoutMs: 5000 });
  if (!draft.includes(promptId)) {
    throw new Error("prompt_id_not_in_editor");
  }
}

async function diagnoseOne(iab, tool) {
  const promptId = `DIAG_${tool.replace(/\W/g, "").toUpperCase()}_${Date.now()}`;
  const expected = `DIAG_OK_${tool.replace(/\W/g, "").toUpperCase()}_${Date.now()}`;
  const prompt = tool === "Gemini"
    ? `PROMPT_ID=${promptId}\nPlease reply with exactly this one line: ${expected}`
    : `PROMPT_ID=${promptId}\n请只回复这一行：${expected}`;
  const tab = await iab.tabs.new();
  const result = { tool, promptId, expected, status: "unknown" };
  try {
    if (tool === "豆包") {
      await tab.goto("https://www.doubao.com/chat/?channel=browser_landing_page");
      await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 20000 }).catch(() => {});
      await tab.playwright.waitForTimeout(4000);
      result.before = await probePage(tab, tool);
      const beforeUrl = await tab.url();
      const before = await tab.playwright.evaluate(() => document.body?.innerText || "", null, { timeoutMs: 10000 }).catch(() => "");
      const input = tab.playwright.locator("textarea").filter({ visible: true });
      await fillTextarea(tab, input, prompt, promptId);
      await input.press("Enter", { timeoutMs: 10000 });
      result.after = await waitForMarker(tab, promptId, expected, beforeUrl, before.length);
      result.status = result.after.containsExpected ? "ok_answer_captured" : "answer_not_captured";
    } else if (tool === "Gemini") {
      await tab.goto("https://gemini.google.com/app");
      await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 25000 }).catch(() => {});
      await tab.playwright.waitForTimeout(6000);
      result.before = await probePage(tab, tool);
      const beforeUrl = await tab.url();
      const before = await tab.playwright.evaluate(() => document.body?.innerText || "", null, { timeoutMs: 10000 }).catch(() => "");
      const editor = tab.playwright.locator('div.ql-editor[contenteditable="true"][role="textbox"]').filter({ visible: true });
      await pasteEditor(tab, editor, prompt, promptId);
      await editor.press("Enter", { timeoutMs: 10000 });
      result.after = await waitForMarker(tab, promptId, expected, beforeUrl, before.length);
      result.status = result.after.containsExpected ? "ok_answer_captured" : "answer_not_captured";
    } else if (tool === "知乎直答") {
      await tab.goto("https://zhida.zhihu.com/");
      await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 20000 }).catch(() => {});
      await tab.playwright.waitForTimeout(4000);
      result.before = await probePage(tab, tool);
      const beforeUrl = await tab.url();
      const editor = tab.playwright.locator('[contenteditable="true"][role="textbox"]').filter({ visible: true });
      await pasteEditor(tab, editor, prompt, promptId);
      const sendIndex = await tab.playwright.evaluate(() => {
        const visible = (el) => Boolean(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        return Array.from(document.querySelectorAll("div.r-1loqt21.r-1otgn73"))
          .map((el, index) => ({ index, el, rect: el.getBoundingClientRect() }))
          .filter((item) => visible(item.el) && item.rect.y > 200 && item.rect.y < 520)
          .sort((a, b) => b.rect.x - a.rect.x)[0]?.index ?? -1;
      }, null, { timeoutMs: 10000 });
      if (sendIndex < 0) {
        throw new Error("zhida_send_control_not_found");
      }
      await tab.playwright.locator("div.r-1loqt21.r-1otgn73").nth(sendIndex).click({ timeoutMs: 10000 });
      result.after = await waitForMarker(tab, promptId, expected, beforeUrl, prompt.length);
      result.newSearchRoute = /\/search\//.test(result.after.finalUrl || "");
      result.status = result.newSearchRoute && result.after.containsExpected ? "ok_new_search_answer_captured" : "route_or_answer_not_captured";
    } else if (tool === "点点") {
      await tab.goto("https://www.xiaohongshu.com/ai_chat");
      await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 25000 }).catch(() => {});
      await tab.playwright.waitForTimeout(6000);
      result.before = await probePage(tab, tool);
      const input = tab.playwright.locator('textarea[name="aiSearchTextarea"]').filter({ visible: true });
      const inputCount = await input.count().catch(() => 0);
      result.visibleAiSearchTextareaCount = inputCount;
      if (inputCount !== 1) {
        throw new Error(`diandian_ai_chat_entry_not_reached:visible_aiSearchTextarea_${inputCount}`);
      }
      const beforeUrl = await tab.url();
      const before = await tab.playwright.evaluate(() => document.body?.innerText || "", null, { timeoutMs: 10000 }).catch(() => "");
      await fillTextarea(tab, input, prompt, promptId);
      const send = tab.playwright.locator(".ai-chat-welcome__input .submit-button-wrapper").filter({ visible: true });
      if ((await send.count().catch(() => 0)) !== 1) {
        throw new Error("diandian_scoped_send_not_unique");
      }
      await send.click({ timeoutMs: 10000 });
      result.after = await waitForMarker(tab, promptId, expected, beforeUrl, before.length);
      result.status = result.after.containsExpected ? "ok_answer_captured" : "answer_not_captured";
    } else {
      throw new Error(`unsupported_tool:${tool}`);
    }
  } catch (error) {
    result.status = "error";
    result.error = String(error?.message || error);
    result.errorProbe = await probePage(tab, tool).catch((probeError) => ({ error: String(probeError?.message || probeError) }));
  } finally {
    result.finalUrl = await tab.url().catch(() => "");
    await tab.close().catch(() => {});
  }
  return result;
}

export async function runPlatformDiagnostics({ iab, outputRoot, tools = ["豆包", "Gemini", "知乎直答", "点点"] }) {
  if (!iab) {
    throw new Error("iab binding is required");
  }
  const runDir = path.join(outputRoot, `platform_diagnostics_v046_${safeStamp()}`);
  await mkdir(runDir, { recursive: true });
  const results = [];
  for (const tool of tools) {
    const result = await diagnoseOne(iab, tool);
    results.push(result);
    await writeFile(path.join(runDir, `${tool}_diag.json`.replace(/[\\/:*?"<>|]/g, "_")), JSON.stringify(result, null, 2), "utf8");
  }
  await writeFile(path.join(runDir, "diagnostics_summary.json"), JSON.stringify(results, null, 2), "utf8");
  return { runDir, results };
}
