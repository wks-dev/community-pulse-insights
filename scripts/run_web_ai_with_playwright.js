#!/usr/bin/env node
/*
 * Submit game polling prompt packs to logged-in Web AI pages with Playwright.
 *
 * This runner is intentionally conservative:
 * - It uses a dedicated persistent browser profile by default.
 * - It never reads or exports cookies, tokens, passwords, or browser storage.
 * - It does not bypass login, CAPTCHA, 403, paywalls, or private content.
 * - It saves raw page text and best-effort parsed JSON for every prompt.
 */

const fs = require("fs");
const path = require("path");

const AI_SITES = {
  "元宝": "https://yuanbao.tencent.com/chat/naQivTmsDa",
  "豆包": "https://www.doubao.com/chat/?channel=browser_landing_page",
  "文心一言": "https://wenxin.baidu.com/",
  "点点": "https://www.xiaohongshu.com/ai_chat",
  "知乎直答": "https://zhida.zhihu.com/",
  "千问": "https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5",
  Gemini: "https://gemini.google.com/app",
  Grok: "https://grok.com/",
};

const ENTRY_SITES = {
  "点点": "https://www.xiaohongshu.com/",
};

const INPUT_SELECTORS = {
  "元宝": [".ql-editor[contenteditable='true']", ".ql-editor", "[role='textbox']"],
  "豆包": ["textarea[placeholder='发消息...']", "textarea.semi-input-textarea", "textarea"],
  "文心一言": ["textarea#chat-textarea", "textarea.ci-textarea", "textarea"],
  "点点": ["textarea[name='aiSearchTextarea']:not([aria-hidden='true'])", "textarea[name='aiSearchTextarea']", "textarea"],
  "知乎直答": ["div.public-DraftEditor-content[role='textbox']", "[role='textbox'].public-DraftEditor-content", "[role='textbox']"],
  "千问": ["div[role='textbox'][contenteditable='true']", "[contenteditable='true'][role='textbox']", "[role='textbox']"],
  Gemini: ["div[aria-label='Enter a prompt for Gemini'][role='textbox']", "div.ql-editor[role='textbox']", "[role='textbox'][contenteditable='true']"],
  Grok: ["div[aria-label='Ask Grok anything'][role='textbox']", "div[role='textbox'][contenteditable='true']", "[role='textbox']"],
};

const SEND_SELECTORS = {
  "元宝": ["#yuanbao-send-btn", "a#yuanbao-send-btn"],
  "豆包": ["button[aria-label*='发送']", "button[aria-label*='Send']", "div[class*='send' i]", ".container-YCWnMI"],
  "文心一言": [".ci-submit-button", "#ci-submit-button-ai", ".ci-submit-button-ai-active"],
  "点点": [".submit-button-wrapper", ".bottom-box-right-submit-button"],
  "知乎直答": ["button[aria-label*='发送']", "div.r-1loqt21.r-1otgn73"],
  "千问": ["button[aria-label*='发送']", "button[type='submit']", "button[class*='send' i]"],
  Gemini: ["button[aria-label*='Send']", "button[aria-label*='Submit']", "button[aria-label*='发送']"],
  Grok: ["button[type='submit']", "button[aria-label*='Submit']", "button[aria-label*='Send']"],
};

// These two sites expose duplicate or unrelated controls. Never fall back to a
// generic textarea, unlabeled button, or Enter key for them.
const STRICT_INPUT_SELECTORS = {
  "点点": ["textarea[name='aiSearchTextarea']"],
  "文心一言": ["textarea#chat-textarea.ci-textarea"],
};
const STRICT_SEND_SELECTORS = {
  "点点": [".ai-chat-welcome__input .submit-button-wrapper", ".textarea-container.ai-chat-input-box .submit-button-wrapper"],
  "文心一言": ["#ci-submit-button-ai.ci-submit-button-ai-active"],
};

function parseArgs(argv) {
  const args = {
    promptPack: "prompt_pack.json",
    outputDir: "daily_ai_outputs/raw",
    profileDir: process.env.PW_AI_PROFILE || path.join(process.cwd(), ".pw-ai-profile"),
    chromePath: process.env.CHROME_PATH || "",
    tools: "",
    limit: 0,
    responseWaitMs: 120000,
    holdMs: 15000,
    headless: false,
    submit: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--submit") {
      args.submit = true;
      continue;
    }
    if (arg === "--headless") {
      args.headless = true;
      continue;
    }
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
    const value = argv[index + 1];
    index += 1;
    if (["limit", "responseWaitMs", "holdMs"].includes(key)) {
      args[key] = Number(value);
    } else {
      args[key] = value;
    }
  }
  return args;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function sanitizeName(value) {
  return String(value || "item").replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 120);
}

function loadPlaywright() {
  const attempts = [];
  if (process.env.PLAYWRIGHT_MODULE) attempts.push(process.env.PLAYWRIGHT_MODULE);
  attempts.push("playwright");
  const nodeRoot = path.resolve(path.dirname(process.execPath), "..");
  attempts.push(path.join(nodeRoot, "node_modules", "playwright"));
  attempts.push(path.join(nodeRoot, "node_modules", ".pnpm", "playwright@1.61.1", "node_modules", "playwright"));
  for (const candidate of attempts) {
    try {
      return require(candidate);
    } catch (_) {
      // Try the next candidate.
    }
  }
  throw new Error(`Cannot load Playwright. Tried: ${attempts.join(", ")}`);
}

function findChrome(explicitPath) {
  const candidates = [
    explicitPath,
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    process.env.PLAYWRIGHT_CHROME_PATH,
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return "";
}

function loadPromptPack(file) {
  const data = JSON.parse(fs.readFileSync(file, "utf-8"));
  if (!Array.isArray(data.prompts)) {
    throw new Error(`No prompts array found in ${file}`);
  }
  return data;
}

function selectedPrompts(pack, args) {
  const requested = args.tools ? new Set(args.tools.split(",").map((item) => item.trim()).filter(Boolean)) : null;
  let prompts = requested ? pack.prompts.filter((item) => requested.has(item.ai_tool)) : pack.prompts.slice();
  if (args.limit > 0) prompts = prompts.slice(0, args.limit);
  return prompts;
}

async function firstVisibleEnabled(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const item = locator.nth(index);
      const visible = await item.isVisible().catch(() => false);
      const enabled = await item.isEnabled().catch(() => true);
      if (visible && enabled) return { locator: item, selector, count, index };
    }
  }
  return null;
}

async function uniqueVisibleEnabled(page, selectors, label) {
  const matches = [];
  for (const selector of selectors) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const item = locator.nth(index);
      if ((await item.isVisible().catch(() => false)) && (await item.isEnabled().catch(() => true))) {
        matches.push({ locator: item, selector, index });
      }
    }
  }
  if (matches.length !== 1) {
    throw new Error(`${label} requires exactly one visible enabled control; found ${matches.length}`);
  }
  return matches[0];
}

async function openAiPage(page, item) {
  const aiUrl = item.url || AI_SITES[item.ai_tool];
  if (!aiUrl) throw new Error(`No URL configured for AI tool: ${item.ai_tool}`);
  const entryUrl = item.entry_url || ENTRY_SITES[item.ai_tool] || "";
  const entryLog = {
    mode: item.entry_mode || (entryUrl ? "open_entry_then_launch_ai" : "direct"),
    entry_url: entryUrl,
    ai_url: aiUrl,
    opened_entry: false,
    launched_from_entry: false,
  };

  if (entryUrl && item.ai_tool === "点点") {
    await page.goto(entryUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    entryLog.opened_entry = true;
    await page.waitForTimeout(3000);
    const launcher = page.locator("a[href*='/ai_chat'], a:has-text('点点'), button:has-text('点点')").first();
    if ((await launcher.count().catch(() => 0)) > 0) {
      await launcher.click({ timeout: 10000 }).catch(async () => {
        await page.goto(aiUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
      });
    } else {
      await page.goto(aiUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    }
    entryLog.launched_from_entry = true;
  } else {
    await page.goto(aiUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  }
  await page.waitForTimeout(4000);
  return entryLog;
}

async function fillPrompt(page, aiTool, prompt) {
  const selectors = STRICT_INPUT_SELECTORS[aiTool] || INPUT_SELECTORS[aiTool] || ["textarea", "[role='textbox']", "[contenteditable='true']"];
  const found = STRICT_INPUT_SELECTORS[aiTool]
    ? await uniqueVisibleEnabled(page, selectors, `${aiTool} input`)
    : await firstVisibleEnabled(page, selectors);
  if (!found) throw new Error(`No visible input found for ${aiTool}`);
  await found.locator.click({ timeout: 10000 });
  try {
    await found.locator.fill("", { timeout: 10000 });
  } catch (_) {
    await found.locator.press("Control+A").catch(() => {});
    await found.locator.press("Backspace").catch(() => {});
  }
  try {
    await found.locator.fill(prompt, { timeout: 25000 });
  } catch (_) {
    await found.locator.type(prompt, { timeout: 60000 });
  }
  const typed = await found.locator.evaluate((el) => el.value || el.innerText || el.textContent || "").catch(() => "");
  if (!typed.includes(prompt.slice(0, Math.min(prompt.length, 40)))) {
    throw new Error(`Input verification failed for ${aiTool}`);
  }
  return found;
}

async function clickSend(page, aiTool, input) {
  if (STRICT_SEND_SELECTORS[aiTool]) {
    const found = await uniqueVisibleEnabled(page, STRICT_SEND_SELECTORS[aiTool], `${aiTool} send control`);
    await found.locator.click({ timeout: 10000 });
    return { method: "strict_dom_click", selector: found.selector, index: found.index };
  }
  const selectors = SEND_SELECTORS[aiTool] || ["button[type='submit']", "button[aria-label*='Send']", "button[aria-label*='发送']"];
  for (const selector of selectors) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);
    const indexes = Array.from({ length: count }, (_, index) => index);
    if (aiTool === "豆包" || aiTool === "知乎直答") indexes.reverse();
    for (const index of indexes) {
      const item = locator.nth(index);
      const visible = await item.isVisible().catch(() => false);
      const enabled = await item.isEnabled().catch(() => true);
      if (!visible || !enabled) continue;
      await item.click({ timeout: 10000 });
      return { method: "dom_click", selector, index };
    }
  }
  await input.locator.press("Enter", { timeout: 10000 });
  return { method: "input_enter_fallback" };
}

function extractJsonObject(text) {
  const fenced = text.match(/```json\s*([\s\S]*?)```/i);
  const raw = fenced ? fenced[1] : text;
  const parsed = [];
  for (let start = 0; start < raw.length; start += 1) {
    if (raw[start] !== "{") continue;
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let index = start; index < raw.length; index += 1) {
      const ch = raw[index];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === "\"") inString = false;
      } else if (ch === "\"") {
        inString = true;
      } else if (ch === "{") {
        depth += 1;
      } else if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          try {
            parsed.push(JSON.parse(raw.slice(start, index + 1)));
          } catch (_) {
            // Continue scanning.
          }
          break;
        }
      }
    }
  }
  const withEvidence = parsed.filter((item) => item && typeof item === "object" && (Array.isArray(item.evidence) || Array.isArray(item.items)));
  return withEvidence.length ? withEvidence[withEvidence.length - 1] : parsed[parsed.length - 1] || null;
}

async function runLoginCheck(context, tools, args) {
  const results = [];
  for (const tool of tools) {
    const page = await context.newPage();
    const startedAt = new Date().toISOString();
    let status = "opened";
    let error = "";
    try {
      await openAiPage(page, { ai_tool: tool, url: AI_SITES[tool], entry_url: ENTRY_SITES[tool] || "" });
      await page.waitForTimeout(args.holdMs);
    } catch (err) {
      status = "error";
      error = String(err.message || err);
    }
    results.push({ ai_tool: tool, status, error, title: await page.title().catch(() => ""), final_url: page.url(), checked_at: startedAt });
    await page.close().catch(() => {});
  }
  return results;
}

async function runSubmit(context, prompts, args) {
  ensureDir(args.outputDir);
  const results = [];
  for (const item of prompts) {
    const page = await context.newPage();
    const baseName = sanitizeName(item.raw_output_path ? path.basename(item.raw_output_path, ".json") : item.prompt_id);
    const rawPath = path.join(args.outputDir, `${baseName}.md`);
    const jsonPath = path.join(args.outputDir, `${baseName}.json`);
    const screenshotPath = path.join(args.outputDir, `${baseName}.png`);
    const startedAt = new Date().toISOString();
    try {
      const entry = await openAiPage(page, item);
      const input = await fillPrompt(page, item.ai_tool, item.prompt);
      const submitMethod = await clickSend(page, item.ai_tool, input);
      await page.waitForTimeout(args.responseWaitMs);
      const bodyText = await page.locator("body").innerText({ timeout: 10000 });
      fs.writeFileSync(rawPath, bodyText, "utf-8");
      const parsed = extractJsonObject(bodyText);
      if (parsed) fs.writeFileSync(jsonPath, `${JSON.stringify(parsed, null, 2)}\n`, "utf-8");
      await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
      results.push({
        prompt_id: item.prompt_id,
        game_id: item.game_id,
        game_name: item.game_name,
        ai_tool: item.ai_tool,
        status: "submitted",
        entry,
        submit_method: submitMethod,
        raw_output: rawPath,
        json_output: parsed ? jsonPath : "",
        screenshot: fs.existsSync(screenshotPath) ? screenshotPath : "",
        started_at: startedAt,
        finished_at: new Date().toISOString(),
      });
    } catch (err) {
      const message = String(err.message || err);
      const pageText = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
      fs.writeFileSync(rawPath, `ERROR: ${message}\n\nPAGE_TEXT:\n${pageText}\n`, "utf-8");
      await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
      results.push({
        prompt_id: item.prompt_id,
        game_id: item.game_id,
        game_name: item.game_name,
        ai_tool: item.ai_tool,
        status: "error",
        error: message,
        raw_output: rawPath,
        screenshot: fs.existsSync(screenshotPath) ? screenshotPath : "",
        started_at: startedAt,
        finished_at: new Date().toISOString(),
      });
    } finally {
      await page.close().catch(() => {});
    }
  }
  return results;
}

async function main() {
  const args = parseArgs(process.argv);
  const { chromium } = loadPlaywright();
  const chromePath = findChrome(args.chromePath);
  const context = await chromium.launchPersistentContext(args.profileDir, {
    executablePath: chromePath || undefined,
    headless: args.headless,
    viewport: { width: 1360, height: 920 },
    args: ["--no-first-run", "--disable-default-apps"],
  });

  try {
    let results;
    if (args.submit) {
      const pack = loadPromptPack(args.promptPack);
      const prompts = selectedPrompts(pack, args);
      if (!prompts.length) throw new Error("No prompts selected");
      results = await runSubmit(context, prompts, args);
    } else {
      const tools = args.tools ? args.tools.split(",").map((item) => item.trim()).filter(Boolean) : Object.keys(AI_SITES);
      results = await runLoginCheck(context, tools, args);
    }
    ensureDir(args.outputDir);
    const summaryPath = path.join(args.outputDir, args.submit ? "playwright_submit_summary.json" : "playwright_login_check.json");
    fs.writeFileSync(summaryPath, `${JSON.stringify({ submit: args.submit, profile_dir: args.profileDir, results }, null, 2)}\n`, "utf-8");
    console.log(JSON.stringify({ ok: true, submit: args.submit, output: summaryPath, count: results.length }, null, 2));
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
