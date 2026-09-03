#!/usr/bin/env python3
"""Convert mixed Web AI raw replies into a renderable daily report payload.

This preview-only helper is deliberately tolerant: it accepts strict JSON,
JSON buried in Markdown/editor text, and URL-bearing prose. It never promotes
URL-less prose to core evidence; URL-less observations remain pending leads or
auxiliary samples in the renderer.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from audit_raw_quality import audit_file, summarize_audit, write_audit_outputs
from load_game_list import read_spreadsheet


URL_RE = re.compile(r"https?://[^\s\]）)》>\"'，。；、]+", re.IGNORECASE)
TRUNCATED_URL_NETLOCS = {
    "zhihu.co",
    "www.zhihu.co",
}

KNOWN_GAMES: list[tuple[str, str, str]] = [
    ("米哈游", "原神", "Genshin Impact"),
    ("米哈游", "崩坏：星穹铁道", "Honkai: Star Rail HSR 星铁 星穹铁道"),
    ("米哈游", "绝区零", "Zenless Zone Zero ZZZ"),
    ("米哈游", "崩坏3", "Honkai Impact 3rd"),
    ("米哈游", "未定事件簿", "Tears of Themis"),
    ("米哈游", "崩坏学园2", "Houkai Gakuen 2"),
    ("米哈游", "崩坏：因缘精灵", "Honkai: Nexus Anima"),
    ("米哈游", "星布谷地", "Petit Planet"),
    ("米哈游", "Varsapura", "雨之城"),
    ("库洛", "鸣潮", "Wuthering Waves WuWa"),
    ("库洛", "战双帕弥什", "Punishing Gray Raven PGR"),
]

AMBIGUOUS_ALIAS_TOKENS = {"2", "3", "the", "of", "impact", "origin"}

AI_PRODUCT_MARKERS = [
    "千问 - 阿里旗下全能AI助手",
    "千问-阿里 AI 助手",
    "Qwen",
    "通义千问",
    "阿里 AI 助手",
    "API 服务",
    "下载电脑端",
    "PPT创作",
    "AI生图",
    "AI生视频",
]

GENERAL_PROMPT_DRIFT_MARKERS = [
    "AUTOMATION_MARKER",
    "COLLECT_RUN_ID=",
    "PROMPT_ID=",
    "帖子/视频/问答/新闻/公告标题",
    "帖子 / 视频 / 问答 / 新闻 / 公告标题",
    "这件事是什么，用大白话说明",
    "只基于证据的一句话说明",
    "https://...",
    "网页简报",
    "产品简报",
    "文档内容",
    "人工智能发展简史",
    "生成一份网页",
    "HTML代码",
    "品牌形象页面",
    "AI搜索能力",
    "通用模板",
]

REFUSAL_MARKERS = [
    "网络安全相关法律法规",
    "翻墙",
    "跨境访问",
    "违法行为",
    "无法为你提供",
    "严格遵守国家网络管理",
]

PLACEHOLDER_TEMPLATE_MARKERS = [
    "帖子/视频/问答/新闻/公告标题",
    "帖子 / 视频 / 问答 / 新闻 / 公告标题",
    "YYYY-MM-DD 或可核查的相对时间",
    "只基于证据的一句话说明",
    "这件事是什么，用大白话说明",
    "玩家对剧情、角色、玩法、优化、付费或运营的具体意见",
    "为什么今天值得关注",
    "core_evidence | auxiliary_sample | pending_lead",
    "accessible | search_snippet_only",
    "无URL、待验证或访问受限的线索",
    "本周期没有找到具体公开信息/社区讨论",
]


def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def read_json_or_text(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except Exception:
        return {"response_text": text, "status": "raw_text"}


def clean_invisible(text: Any) -> str:
    return (
        str(text or "")
        .replace("\u00a0", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )


def normalize_url(value: Any) -> str:
    url = str(value or "").strip().strip(".,;，。；、")
    lowered = url.casefold()
    if not url or "https://..." in url or any(marker in lowered for marker in ["示例", "样例", "placeholder", "example url"]):
        return ""
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    if parts.netloc.lower() in TRUNCATED_URL_NETLOCS:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def strip_editor_noise(text: str) -> str:
    lines: list[str] = []
    for line in clean_invisible(text).splitlines():
        stripped = line.strip()
        if stripped in {"json", "编辑", "复制代码", "复制"}:
            continue
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def parse_json_candidates(text: str) -> list[dict[str, Any]]:
    raw = strip_editor_noise(text)
    candidates: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL):
        candidates.append(match.group(1).strip())
    starts = [match.start() for match in re.finditer(r"\{", raw)]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(raw)):
            char = raw[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(raw[start : index + 1])
                    break
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate[:200]
        if key in seen:
            continue
        seen.add(key)
        try:
            value = json.loads(candidate)
        except Exception:
            continue
        if isinstance(value, dict):
            parsed.append(value)
    return parsed


JSONISH_FIELDS = [
    "company",
    "category",
    "sector",
    "sector_item",
    "is_watch_matrix_game",
    "is_key_company",
    "game_name",
    "matched_alias",
    "product_tier",
    "game_status",
    "scope",
    "platform",
    "source_ai",
    "title",
    "url",
    "published_at",
    "event_type",
    "player_tendency",
    "sentiment",
    "risk_level",
    "summary",
    "plain_summary",
    "specific_player_opinions",
    "why_watch",
    "business_use",
    "evidence_level",
    "access_status",
    "limitations",
    "not_hit_reason",
]


def section_after_last_ai_json(text: str) -> str:
    """Prefer the actual answer block over the echoed prompt contract."""
    raw = strip_editor_noise(text)
    starts = [
        raw.rfind('\n{\n"ai_tool"'),
        raw.rfind('{\n"ai_tool"'),
        raw.rfind('\n{\r\n"ai_tool"'),
        raw.rfind('{\r\n"ai_tool"'),
    ]
    start = max(starts)
    return raw[start:] if start >= 0 else raw


def jsonish_array_section(text: str, key: str, next_key: str | None = None) -> str:
    raw = section_after_last_ai_json(text)
    marker = f'"{key}"'
    pos = raw.rfind(marker)
    if pos < 0:
        return ""
    start = raw.find("[", pos)
    if start < 0:
        return ""
    if next_key:
        next_pos = raw.find(f'"{next_key}"', start)
        if next_pos > start:
            end = raw.rfind("]", start, next_pos)
            if end > start:
                return raw[start + 1 : end]
    depth = 0
    for index in range(start, len(raw)):
        char = raw[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return raw[start + 1 : index]
    return ""


def object_blocks(section: str) -> list[str]:
    blocks: list[str] = []
    start: int | None = None
    depth = 0
    for index, char in enumerate(section):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    blocks.append(section[start : index + 1])
                    start = None
    return blocks


def unquote_jsonish_value(value: str) -> str:
    raw = value.strip().rstrip(",").strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        raw = raw[1:-1]
    raw = raw.replace('\\"', '"').replace("\\n", " ").replace("\\/", "/")
    return compact(raw, 900)


def fields_from_jsonish_object(block: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key_part, value_part = line.split(":", 1)
        key = key_part.strip().strip('"')
        if key not in JSONISH_FIELDS:
            continue
        row[key] = unquote_jsonish_value(value_part)
    return row


def rows_from_jsonish_text(text: str, source: dict[str, Any], source_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Parse line-oriented JSON-like replies when strict JSON fails.

    Some Web AI pages copy generated JSON through an editor view and may leave
    unescaped quotes inside a title. Standard JSON parsing then fails, but the
    one-field-per-line shape is still recoverable.
    """
    source_ai = source.get("ai_tool") or ""
    evidence: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    for block in object_blocks(jsonish_array_section(text, "evidence", "pending_leads")):
        row = fields_from_jsonish_object(block)
        if not row or is_placeholder(row):
            continue
        row.setdefault("source_ai", source_ai)
        row.setdefault("source_file", str(source_file))
        row.setdefault("extraction_method", "jsonish_line_payload")
        evidence.append(row)

    for block in object_blocks(jsonish_array_section(text, "pending_leads", "expanded_keywords")):
        row = fields_from_jsonish_object(block)
        if not row or is_placeholder(row):
            continue
        row.setdefault("source_ai", source_ai)
        row.setdefault("source_file", str(source_file))
        pending.append(row)

    return evidence, pending, len(evidence) + len(pending)


KV_FIELD_ALIASES = {
    "company/category": "category",
    "company": "company",
    "category": "category",
    "game_name": "game_name",
    "matched_alias": "matched_alias",
    "event_type": "event_type",
    "title": "title",
    "plain_summary": "plain_summary",
    "specific_player_opinions": "specific_player_opinions",
    "why_watch": "why_watch",
    "business_use": "business_use",
    "url": "url",
    "evidence_level": "evidence_level",
    "risk_level": "risk_level",
    "limitations": "limitations",
    "游戏名": "game_name",
    "公司": "company",
    "分类": "category",
    "事件": "title",
    "标题": "title",
    "玩家反馈": "specific_player_opinions",
    "为什么值得关注": "why_watch",
    "业务使用": "business_use",
    "可核验来源": "limitations",
    "url或无url说明": "limitations",
    "风险等级": "risk_level",
}


KV_FIELD_ALIASES.update(
    {
        "公司": "company",
        "游戏名": "game_name",
        "标题或事件": "title",
        "事件标题": "title",
        "事件": "title",
        "标题": "title",
        "平台": "platform",
        "发布时间": "published_at",
        "发布日期": "published_at",
        "时间": "published_at",
        "时间线索": "published_at",
        "发布时间或时间线索": "published_at",
        "玩家倾向": "player_tendency",
        "玩家具体意见": "specific_player_opinions",
        "玩家具体观点": "specific_player_opinions",
        "玩家反馈": "specific_player_opinions",
        "核心内容": "plain_summary",
        "大白话摘要": "plain_summary",
        "大白话说明": "plain_summary",
        "为什么值得关注": "why_watch",
        "业务使用": "business_use",
        "公开链接": "url",
        "链接": "url",
        "URL": "url",
        "url": "url",
        "风险等级": "risk_level",
        "限制": "limitations",
        "样本限制": "limitations",
        "limitations": "limitations",
    }
)


INLINE_KV_RE = re.compile(
    r"(公司|游戏名|标题或事件|事件标题|标题|事件|平台|发布时间或时间线索|发布时间|发布日期|时间线索|时间|玩家倾向|玩家具体意见|玩家具体观点|玩家反馈|核心内容|大白话摘要|大白话说明|为什么值得关注|业务使用|公开链接|链接|URL|url|风险等级|限制|样本限制|limitations)\s*[:：]"
)


def answer_like_tail(text: str) -> str:
    """Drop visible sidebars and echoed prompt preambles when a clear answer anchor exists."""
    raw = clean_invisible(text)
    anchors = [
        "以下是基于最近",
        "以下是2026",
        "以下是 2026",
        "以下为基于最近",
        "以下为",
        "根据最近",
        "根据公开",
    ]
    starts = [raw.find(anchor) for anchor in anchors if raw.find(anchor) >= 0]
    return raw[min(starts) :] if starts else raw


def extract_inline_kv_fields(block: str) -> dict[str, Any]:
    """Parse Chinese key/value fields even when the DOM collapses them onto one line."""
    cleaned = clean_invisible(block)
    row: dict[str, Any] = {}
    matches = list(INLINE_KV_RE.finditer(cleaned))
    for index, match in enumerate(matches):
        key = match.group(1).strip()
        mapped = KV_FIELD_ALIASES.get(key) or KV_FIELD_ALIASES.get(key.lower())
        if not mapped:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        value = cleaned[match.end() : end].replace("__ITEM__", "").strip(" \t\r\n-：:")
        if mapped == "url":
            url_match = URL_RE.search(value)
            if url_match:
                row["url"] = url_match.group(0)
            elif value:
                row["limitations"] = compact(f"{row.get('limitations', '')} URL field did not contain a real link: {value}", 260)
            continue
        if value:
            row[mapped] = compact(value, 900)

    first_line = next((line.strip() for line in cleaned.splitlines() if line.strip()), "")
    title_match = re.match(r"^\s*\d{1,2}[.、)]\s*(.+)$", first_line)
    if title_match and not row.get("title"):
        row["title"] = compact(title_match.group(1), 180)
    return row


def split_numbered_answer_blocks(text: str) -> list[str]:
    raw = answer_like_tail(text)
    matches = list(re.finditer(r"(?m)^\s*\d{1,2}[.、)]\s+(?=\S)", raw))
    blocks: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        blocks.append(raw[match.start() : end].strip())
    if not blocks:
        blocks = re.split(r"(?m)^\s*(?:__ITEM__)\s*$", raw)
    return blocks


def rows_from_numbered_kv_text(text: str, source: dict[str, Any], source_file: Path) -> tuple[list[dict[str, Any]], int]:
    """Parse numbered key/value blocks such as Grok's short supplement output."""
    source_ai = source.get("ai_tool") or ""
    raw = clean_invisible(text)
    raw = re.sub(r"(?m)^\s*(game_name|游戏名)\s*[:：]\s*", "\n__ITEM__\ngame_name: ", raw)
    blocks = split_numbered_answer_blocks(raw)
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if is_prompt_context(block):
            continue
        row: dict[str, Any] = extract_inline_kv_fields(block)
        current_key = ""
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^(深度思考|分析|关注|请补充|Fast|任务|AI生图|AI写作|AI PPT|更多|内容由AI生成)", stripped):
                break
            match = re.match(r"^([^:：]{1,40})[:：]\s*(.*)$", stripped)
            if match:
                key_part, value_part = match.groups()
                mapped = KV_FIELD_ALIASES.get(key_part.strip().strip('"').lower())
                if mapped:
                    row[mapped] = compact(value_part.strip(), 900)
                    current_key = mapped
                    continue
            if current_key and not re.match(r"^\s*\d+\s*$", stripped):
                row[current_key] = compact(f"{row.get(current_key, '')} {stripped}", 900)
        if not row or is_placeholder(row):
            continue
        if not (row.get("game_name") and (row.get("title") or row.get("plain_summary") or row.get("url"))):
            continue
        if str(row.get("game_name") or "").strip() in {"具体游戏名", "二游大盘主题"}:
            continue
        if "__ITEM__" in str(row.get("company") or ""):
            row["company"] = compact(str(row.get("company") or "").split("__ITEM__", 1)[0], 80)
        category = str(row.get("category") or "")
        if not row.get("company"):
            if "米哈游" in category:
                row["company"] = "米哈游"
            elif "库洛" in category:
                row["company"] = "库洛"
            else:
                row["company"] = "二游大盘"
        row.setdefault("matched_alias", row.get("game_name") or "")
        if row.get("title") and not row.get("plain_summary"):
            row["plain_summary"] = row["title"]
        if row.get("plain_summary") and not row.get("why_watch"):
            row["why_watch"] = "该线索来自当前平台的编号结果，缺少真实 URL 时需先人工核验。"
        if row.get("plain_summary") and not row.get("business_use"):
            row["business_use"] = "可作为内部讨论备选线索；无 URL 时不建议直接外发。"
        if row.get("limitations") and not row.get("url"):
            match = URL_RE.search(str(row.get("limitations") or ""))
            if match:
                row["url"] = match.group(0)
        row.setdefault("evidence_level", "core_evidence" if row.get("url") else "pending_lead")
        row.setdefault("source_ai", source_ai)
        row.setdefault("source_file", str(source_file))
        row.setdefault("extraction_method", "numbered_kv_text")
        rows.append(row)
    return rows, len(rows)


def is_placeholder(item: dict[str, Any]) -> bool:
    text = " ".join(str(item.get(key) or "") for key in ["title", "url", "summary", "lead", "published_at"])
    return any(
        marker in text
        for marker in [
            "帖子/视频/问答/新闻/公告标题",
            "YYYY-MM-DD",
            "https://...",
            "无 URL、待验证或访问受限的线索",
            "帖子 / 视频 / 问答 / 新闻 / 公告标题",
            "帖子/视频/问答/新闻/公告标题",
            "只基于证据的一句话说明",
            "这件事是什么，用大白话说明",
            "玩家对剧情、角色、玩法、优化、付费或运营的具体意见",
            "为什么今天值得关注",
            "只基于证据的一句话说明",
            "无URL、待验证或访问受限的线索",
        ]
    )


def infer_company_game(text: str) -> tuple[str, str]:
    folded = text.casefold()
    for company, game, aliases in KNOWN_GAMES:
        names = [name for name in [game, aliases, *aliases.split()] if is_safe_game_match_token(name)]
        if any(name and name.casefold() in folded for name in names):
            return company, game
    if "米哈游" in text or "mihoyo" in folded or "hoyoverse" in folded:
        return "米哈游", "米哈游产品矩阵"
    if "库洛" in text or "kuro" in folded:
        return "库洛", "库洛产品矩阵"
    if "二游" in text or "gacha" in folded:
        return "二游大盘", "二游大盘"
    return "其他", "线索"


def is_safe_game_match_token(name: str) -> bool:
    token = str(name or "").strip()
    if not token:
        return False
    folded = token.casefold()
    if folded in AMBIGUOUS_ALIAS_TOKENS or folded.isdigit():
        return False
    if token.isascii() and len(folded) < 3:
        return False
    return True


def infer_key_company_from_row(row: dict[str, Any]) -> tuple[str, str]:
    direct_text = " ".join(str(row.get(field) or "") for field in ["game_name", "matched_alias"])
    company, game = infer_company_game(direct_text)
    if company in {"米哈游", "库洛"}:
        return company, game
    if str(row.get("company") or "").strip() in {"二游大盘", "其他", ""}:
        return "", ""
    context_text = " ".join(str(row.get(field) or "") for field in ["title", "summary", "plain_summary"])
    company, game = infer_company_game(context_text)
    if company in {"米哈游", "库洛"}:
        return company, game
    return "", ""


def infer_platform(text: str, source_ai: str) -> str:
    folded = text.casefold()
    if "xiaohongshu" in folded or "xhslink" in folded or "小红书" in text or "点点" in text:
        return "小红书"
    if "tieba.baidu" in folded or "贴吧" in text:
        return "百度贴吧"
    if "bilibili" in folded or "b23.tv" in folded or "b站" in text or "哔哩" in text:
        return "B站"
    if "weibo" in folded or "微博" in text:
        return "微博"
    if "zhihu" in folded or "知乎" in text:
        return "知乎"
    if "x.com" in folded or "twitter" in folded:
        return "X"
    if "youtube" in folded or "youtu.be" in folded:
        return "YouTube"
    if "taptap" in folded:
        return "TapTap"
    if source_ai == "文心一言":
        return "百度/中文网页"
    if source_ai == "千问":
        return "中文网页"
    return "公开网页"


def infer_sentiment(text: str) -> str:
    if any(word in text for word in ["争议", "差评", "退坑", "不满", "骂", "负面", "风险", "吐槽"]):
        return "negative"
    if any(word in text for word in ["好评", "期待", "推荐", "回流", "喜欢", "正面", "必抽"]):
        return "positive"
    if any(word in text for word in ["分化", "观望", "两极", "mixed"]):
        return "mixed"
    return "neutral"


def infer_risk(text: str) -> str:
    if any(word in text for word in ["高风险", "危机", "公关", "集中差评", "炎上", "大规模"]):
        return "high"
    if any(word in text for word in ["争议", "分化", "退坑", "负面", "不满", "观望"]):
        return "medium"
    return "low"


def compact(text: Any, limit: int = 220) -> str:
    value = re.sub(r"\s+", " ", clean_invisible(text)).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


DEBUG_FRAGMENT_MARKERS = (
    '"game_name"',
    '"matched_alias"',
    '"product_tier"',
    '"game_status"',
    '"source_file"',
    "product_tier",
    "game_status",
    "source_file",
    "AUTOMATION_MARKER",
    "COLLECT_RUN_ID=",
    "PROMPT_ID=",
)


def looks_like_debug_fragment(row: dict[str, Any]) -> bool:
    """Reject prompt echoes and half-parsed JSON fragments before rendering."""
    fields = ["company", "game_name", "title", "summary", "plain_summary", "lead", "url"]
    values = [str(row.get(field) or "") for field in fields]
    blob = " ".join(values)
    if any(looks_like_cross_item_fragment(value) for value in values):
        return True
    if any(marker in blob for marker in DEBUG_FRAGMENT_MARKERS):
        return True
    title = str(row.get("title") or "").strip()
    if title.startswith(('":', "ue,", 'ny":', "true,", "false,")):
        return True
    game_name = str(row.get("game_name") or "").strip()
    if len(game_name) > 80 and any(marker in game_name for marker in ["标题", "事件", "平台", "玩家", "风险"]):
        return True
    summary = str(row.get("summary") or row.get("plain_summary") or "").strip()
    if summary.startswith("待验证线索缺少具体摘要"):
        return True
    if "平台采集失败" in blob:
        return True
    if str(row.get("company") or "") == "平台状态":
        return True
    return False


URL_CONTEXT_FIELD_RE = re.compile(
    r"(?:\u6e38\u620f\u540d|\u6807\u9898|\u6807\u9898\u6216\u4e8b\u4ef6|\u5e73\u53f0|"
    r"\u73a9\u5bb6|\u4e3a\u4ec0\u4e48|\u4e1a\u52a1\u4f7f\u7528|URL|evidence_level|limitations)"
    r"\s*[:\uff1a]",
    flags=re.IGNORECASE,
)


def looks_like_cross_item_fragment(text: Any) -> bool:
    """Reject field-boundary shards produced by URL-context slicing."""
    value = str(text or "").strip()
    if not value:
        return False
    if re.match(r"^(?:tations|mitations|nce_level|dence_level|evidence_level|vel)\s*[:\uff1a]", value, flags=re.IGNORECASE):
        return True
    labels = URL_CONTEXT_FIELD_RE.findall(value)
    if len(labels) >= 4:
        return True
    if len(labels) >= 2 and not re.search(r"(?:^|\n)\s*(?:\d{1,2}[.\u3001]|\u6e38\u620f\u540d\s*[:\uff1a])", value):
        return True
    return False


def normalize_evidence_level(value: Any, has_url: bool, default: str = "core_evidence") -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"core_evidence", "core", "核心证据", "核心證據"}:
        return "core_evidence" if has_url else "pending_lead"
    if raw in {"auxiliary_sample", "auxiliary", "辅助样本", "輔助樣本"}:
        return "auxiliary_sample" if has_url else "pending_lead"
    if raw in {"pending_lead", "pending", "待验证", "待验证线索", "待驗證"}:
        return "pending_lead"
    if has_url and default == "core_evidence":
        return "core_evidence"
    return "pending_lead"


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    return text in {"1", "true", "yes", "y", "是", "yes."}


def is_key_company_value(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in ["米哈游", "mihoyo", "hoyoverse", "库洛", "kuro"])


def looks_like_sector_item(row: dict[str, Any]) -> bool:
    sector = str(row.get("sector") or "").strip().casefold()
    category = str(row.get("category") or "")
    if sector and sector not in {"none", "null", "无", "n/a"}:
        return True
    return any(marker in category for marker in ["赛道", "潜在方向", "共同关注方向"])


def normalize_structured_row(row: dict[str, Any], *, target: str) -> dict[str, Any]:
    """Keep stage-2 fields stable without inventing new facts."""
    out = dict(row)
    url = normalize_url(out.get("url"))
    out["url"] = url

    lead = compact(out.get("lead") or "", 360)
    summary = compact(out.get("summary") or out.get("event_summary") or lead, 360)
    title = compact(out.get("title") or out.get("event_or_discussion") or lead, 180)
    plain = compact(out.get("plain_summary") or summary or title, 360)
    why = compact(out.get("why_watch") or out.get("evidence_support") or "", 300)
    business = compact(out.get("business_use") or why or summary, 300)

    out["summary"] = summary or plain
    out["plain_summary"] = plain
    out["why_watch"] = why
    out["business_use"] = business
    out["limitations"] = compact(out.get("limitations") or ("" if url else "No URL supplied; keep as pending lead until manually verified."), 260)
    out["sector"] = compact(out.get("sector") or ("none" if not looks_like_sector_item(out) else out.get("category") or ""), 80)
    out["sector_item"] = as_bool(out.get("sector_item")) or looks_like_sector_item(out)
    inferred_company, inferred_game = infer_key_company_from_row(out)
    if inferred_company:
        out["company"] = inferred_company
        if inferred_game and inferred_game not in {"米哈游产品矩阵", "库洛产品矩阵"}:
            out["game_name"] = inferred_game
            out.setdefault("matched_alias", inferred_game)
    out["is_key_company"] = (
        as_bool(out.get("is_key_company"))
        or bool(inferred_company)
        or is_key_company_value(out.get("company"))
        or is_key_company_value(out.get("game_status"))
    )
    if "is_watch_matrix_game" not in out:
        out["is_watch_matrix_game"] = False

    if target == "evidence":
        out["evidence_level"] = normalize_evidence_level(out.get("evidence_level"), bool(url), "core_evidence")
        if not url:
            out["evidence_level"] = "pending_lead"
    else:
        out["evidence_level"] = normalize_evidence_level(out.get("evidence_level"), bool(url), "pending_lead")
        if not url:
            out["evidence_level"] = "pending_lead"
        if not out["plain_summary"]:
            out["plain_summary"] = "待验证线索缺少具体摘要，需回看原始输出。"
            out["summary"] = out["summary"] or out["plain_summary"]
        if not out["why_watch"]:
            out["why_watch"] = "信息不足，需人工复核后判断。"
        if not out["business_use"]:
            out["business_use"] = "仅作待核验线索，不建议外部使用。"
    return out


def split_evidence_by_url(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for row in rows:
        if looks_like_debug_fragment(row):
            continue
        normalized = normalize_structured_row(row, target="evidence")
        if looks_like_debug_fragment(normalized):
            continue
        if normalized.get("url") and normalized.get("evidence_level") == "core_evidence":
            evidence.append(normalized)
        else:
            normalized["evidence_level"] = "pending_lead"
            normalized.setdefault("reason", "no_url")
            pending.append(normalized)
    return evidence, pending


def has_real_url(rows: list[dict[str, Any]]) -> bool:
    return any(normalize_url(row.get("url")) for row in rows)


def should_surface_unparsed_pending(data: dict[str, Any], text: str) -> bool:
    """Only show unparsed text when it is not a prompt echo, page shell, or platform debug note."""
    blob = str(text or "")
    if any(marker in blob for marker in ["AUTOMATION_MARKER", "COLLECT_RUN_ID=", "PROMPT_ID="]):
        return False
    if any(marker in blob for marker in ["帖子 / 视频 / 问答 / 新闻 / 公告标题", "帖子/视频/问答/新闻/公告标题", "https://..."]):
        return False
    if str(data.get("status") or "").lower() == "error":
        return False
    return bool(compact(blob, 80))


def placeholder_template_marker_count(text: str) -> int:
    blob = str(text or "")
    return sum(1 for marker in PLACEHOLDER_TEMPLATE_MARKERS if marker in blob)


def has_refusal_marker(text: str) -> bool:
    return any(marker in str(text or "") for marker in REFUSAL_MARKERS)


def strong_prompt_template_or_refusal(text: str) -> bool:
    blob = str(text or "")
    if has_refusal_marker(blob):
        return True
    return placeholder_template_marker_count(blob) >= 4 and not re.search(
        r"事件标题[:：]\s*(?!帖子/视频/问答/新闻/公告标题)\S{4,}",
        blob,
    )


def prompt_drift(data: dict[str, Any], text: str, evidence_count: int) -> bool:
    ai_tool = str(data.get("ai_tool") or "")
    if strong_prompt_template_or_refusal(text):
        return True
    if evidence_count:
        return False
    if any(marker in text for marker in GENERAL_PROMPT_DRIFT_MARKERS):
        return True
    if any(marker in text for marker in AI_PRODUCT_MARKERS):
        return True
    if str(data.get("capture_quality") or "").lower() == "weak" and any(
        marker in str(data.get("error") or "")
        for marker in ["prompt_echo", "answer_drift", "not_captured"]
    ):
        return True
    if ai_tool == "千问" and any(marker in text for marker in AI_PRODUCT_MARKERS):
        return True
    if ai_tool == "千问":
        return "未能检索到" in text and "千问" in text
    if ai_tool == "文心一言":
        return has_refusal_marker(text)
    return False


def infer_company_game_for_event_block(text: str) -> tuple[str, str]:
    if "碧蓝档案" in text or "蔚蓝档案" in text or "Blue Archive" in text:
        return "其他竞品", "蔚蓝档案"
    if "版号" in text or "游戏审批" in text:
        return "二游大盘", "二游大盘"
    return infer_company_game(text)


def rows_from_public_link_event_blocks(text: str, data: dict[str, Any], source_file: Path) -> list[dict[str, Any]]:
    source_ai = str(data.get("ai_tool") or "")
    raw = answer_like_tail(text)
    pattern = re.compile(
        r"事件标题\S*[:：]\s*(?P<title>.*?)\s*"
        r"(?:发布日期|发布时间)\s*[:：]\s*(?P<published_at>.*?)\s*"
        r"(?:公开链接|链接)\s*[:：]\s*(?P<url>https?://[^\s]+)\s*"
        r"(?:核心内容|内容|摘要)\s*[:：]\s*(?P<summary>.*?)(?=\s*事件标题\S*[:：]|\s*需要我|$)",
        flags=re.DOTALL,
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(raw):
        title = compact(match.group("title"), 180)
        summary = compact(match.group("summary"), 420)
        url = normalize_url(match.group("url"))
        if not title or not url:
            continue
        context = f"{title} {summary}"
        if is_prompt_context(context):
            continue
        company, game = infer_company_game_for_event_block(context)
        rows.append(
            {
                "company": company,
                "game_name": game,
                "scope": "market" if company == "二游大盘" else "game",
                "platform": infer_platform(context + " " + url, source_ai),
                "source_ai": source_ai,
                "title": title,
                "url": url,
                "published_at": compact(match.group("published_at"), 80),
                "event_type": infer_event_type(context),
                "player_tendency": infer_player_tendency(context),
                "sentiment": infer_sentiment(context),
                "risk_level": infer_risk(context),
                "summary": summary,
                "plain_summary": summary or title,
                "specific_player_opinions": "",
                "why_watch": "该事件有公开链接支撑，可作为本轮报告的核心证据候选。",
                "business_use": "可用于讨论版本福利、抽卡机制、版号供给或二游市场竞争变化。",
                "access_status": "accessible",
                "limitations": "由文心/网页可见文本中的事件标题、公开链接和核心内容块抽取，仍需人工打开链接复核。",
                "source_file": str(source_file),
                "extraction_method": "public_link_event_block",
            }
        )
    return rows


def evidence_from_url_context(text: str, data: dict[str, Any], source_file: Path) -> list[dict[str, Any]]:
    source_ai = str(data.get("ai_tool") or "")
    event_rows = rows_from_public_link_event_blocks(text, data, source_file)
    if event_rows:
        return event_rows
    rows: list[dict[str, Any]] = []
    for match in URL_RE.finditer(text):
        url = normalize_url(match.group(0))
        if not url:
            continue
        start = max(0, match.start() - 260)
        end = min(len(text), match.end() + 360)
        context = compact(text[start:end], 320)
        if is_prompt_context(context) or looks_like_cross_item_fragment(context):
            continue
        company, game = infer_company_game(context)
        rows.append(
            {
                "company": company,
                "game_name": game,
                "scope": "market" if company == "二游大盘" else "game",
                "platform": infer_platform(context + " " + url, source_ai),
                "source_ai": source_ai,
                "title": first_title_like_line(context) or compact(context, 80),
                "url": url,
                "published_at": infer_date(context),
                "event_type": infer_event_type(context),
                "player_tendency": infer_player_tendency(context),
                "sentiment": infer_sentiment(context),
                "risk_level": infer_risk(context),
                "summary": context,
                "specific_player_opinions": "",
                "why_watch": "从非严格 JSON 原文中抽取 URL 上下文，需人工复核。",
                "access_status": "accessible",
                "limitations": "robust_structure_raw heuristic extraction from raw Web AI prose.",
                "source_file": str(source_file),
                "extraction_method": "heuristic_url_context",
            }
        )
    return rows


def is_prompt_context(text: str) -> bool:
    return any(
        marker in text
        for marker in [
            "AUTOMATION_MARKER",
            "输出必须是严格 JSON",
            "格式如下",
            "硬性要求",
            "当前 Web AI 工具",
            "本轮唯一检索对象",
        ]
    )


def first_title_like_line(text: str) -> str:
    for line in str(text or "").splitlines():
        stripped = line.strip(" -*#：:")
        if 8 <= len(stripped) <= 90 and not stripped.startswith("http"):
            return stripped
    return ""


def infer_date(text: str) -> str:
    match = re.search(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}", text)
    if not match:
        return ""
    return match.group(0).replace("年", "-").replace("月", "-").replace("/", "-").replace(".", "-").rstrip("日")


def infer_event_type(text: str) -> str:
    for key in ["版本", "角色", "剧情", "玩法", "付费", "运营", "活动", "优化", "争议", "BUG"]:
        if key in text:
            return key
    return "其他"


def infer_player_tendency(text: str) -> str:
    for key in ["入坑", "回流", "退坑", "抽卡", "付费", "观望", "建议", "推荐", "争议讨论"]:
        if key in text:
            return key
    return ""


def not_hit_from_payload(payload: dict[str, Any], source: dict[str, Any], source_file: Path) -> list[dict[str, Any]]:
    source_ai = payload.get("ai_tool") or source.get("ai_tool") or ""
    rows: list[dict[str, Any]] = []
    for item in payload.get("not_hit_games") or []:
        if not isinstance(item, dict):
            continue
        game_name = compact(item.get("game_name") or item.get("name") or "", 120)
        reason = compact(item.get("not_hit_reason") or item.get("reason") or "", 260)
        if game_name in {"关注矩阵中的游戏名", "具体游戏名"}:
            continue
        if not game_name and not reason:
            continue
        rows.append(
            {
                "game_name": game_name,
                "matched_alias": compact(item.get("matched_alias") or "", 160),
                "not_hit_reason": reason or "本周期没有找到具体公开信息/社区讨论。",
                "source_ai": source_ai,
                "source_file": str(source_file),
            }
        )
    return rows


def rows_from_payload(payload: dict[str, Any], source: dict[str, Any], source_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_ai = payload.get("ai_tool") or source.get("ai_tool") or ""
    evidence: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for item in payload.get("evidence") or payload.get("items") or payload.get("records") or []:
        if isinstance(item, dict) and not is_placeholder(item) and not looks_like_debug_fragment(item):
            row = dict(item)
            row.setdefault("source_ai", source_ai)
            row.setdefault("source_file", str(source_file))
            row.setdefault("extraction_method", "json_payload")
            evidence.append(row)
    for item in payload.get("pending_leads") or []:
        if isinstance(item, dict) and not is_placeholder(item) and not looks_like_debug_fragment(item):
            row = dict(item)
            row.setdefault("source_ai", source_ai)
            row.setdefault("source_file", str(source_file))
            pending.append(row)
    return evidence, pending


def structure_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    data = read_json_or_text(path)
    if not isinstance(data, dict):
        data = {"response_text": json.dumps(data, ensure_ascii=False), "status": "raw_list"}
    response_text = str(data.get("response_text") or "")
    evidence: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    not_hit_games: list[dict[str, Any]] = []

    collection_status = str(data.get("status") or "").lower()
    prompt_confirmed = bool(data.get("prompt_id_confirmed"))
    if collection_status == "error" and not prompt_confirmed and not data.get("evidence") and not data.get("pending_leads"):
        status = {
            "prompt_id": data.get("prompt_id") or path.stem,
            "ai_tool": data.get("ai_tool") or "",
            "status": data.get("status") or "error",
            "error": data.get("error") or "unconfirmed_send",
            "capture_quality": data.get("capture_quality") or "",
            "capture_quality_detail": data.get("capture_quality_detail") or "",
            "needs_structure_review": bool(data.get("needs_structure_review")),
            "parsed_json_payloads": 0,
            "jsonish_items": 0,
            "numbered_kv_items": 0,
            "heuristic_url_items": 0,
            "evidence_count": 0,
            "pending_count": 0,
            "prompt_drift": False,
            "fallback_recommended": should_recommend_fallback(data, False),
            "not_hit_games": [],
            "source_file": str(path),
        }
        pending.append(
            {
                "company": "平台状态",
                "game_name": str(data.get("ai_tool") or path.stem),
                "lead": f"平台采集失败：{data.get('error') or 'unconfirmed_send'}",
                "reason": "platform_failure",
                "source_ai": data.get("ai_tool") or "",
                "source_file": str(path),
            }
        )
        return [], [], status

    for item in data.get("evidence") or []:
        if isinstance(item, dict) and not is_placeholder(item) and not looks_like_debug_fragment(item):
            row = dict(item)
            row.setdefault("source_ai", data.get("ai_tool"))
            row.setdefault("source_file", str(path))
            row.setdefault("extraction_method", "raw_top_level")
            evidence.append(row)
    for item in data.get("pending_leads") or []:
        if isinstance(item, dict) and not is_placeholder(item) and not looks_like_debug_fragment(item):
            row = dict(item)
            row.setdefault("source_ai", data.get("ai_tool"))
            row.setdefault("source_file", str(path))
            pending.append(row)
    not_hit_games.extend(not_hit_from_payload(data, data, path))

    json_payload_count = 0
    for payload in parse_json_candidates(response_text):
        payload_evidence, payload_pending = rows_from_payload(payload, data, path)
        not_hit_games.extend(not_hit_from_payload(payload, data, path))
        if payload_evidence or payload_pending:
            json_payload_count += 1
            evidence.extend(payload_evidence)
            pending.extend(payload_pending)

    jsonish_count = 0
    if response_text and not evidence:
        jsonish_evidence, jsonish_pending, jsonish_count = rows_from_jsonish_text(response_text, data, path)
        evidence.extend(jsonish_evidence)
        pending.extend(jsonish_pending)

    numbered_kv_count = 0
    if response_text and not has_real_url(evidence):
        numbered_kv_evidence, numbered_kv_count = rows_from_numbered_kv_text(response_text, data, path)
        evidence.extend(numbered_kv_evidence)

    heuristic_rows = []
    if response_text and not has_real_url(evidence) and numbered_kv_count == 0 and jsonish_count == 0:
        heuristic_rows = evidence_from_url_context(response_text, data, path)
        evidence.extend(heuristic_rows)

    drift = prompt_drift(data, response_text, len(evidence) + len(pending))
    if drift:
        evidence = []
        pending = []
    else:
        evidence, moved_pending = split_evidence_by_url(evidence)
        pending.extend(moved_pending)
        pending = [
            normalized
            for row in pending
            if not looks_like_debug_fragment(row)
            for normalized in [normalize_structured_row(row, target="pending")]
            if not looks_like_debug_fragment(normalized)
        ]

    status = {
        "prompt_id": data.get("prompt_id") or path.stem,
        "ai_tool": data.get("ai_tool") or "",
        "status": data.get("status") or "unknown",
        "error": data.get("error") or "",
        "capture_quality": data.get("capture_quality") or "",
        "capture_quality_detail": data.get("capture_quality_detail") or "",
        "needs_structure_review": bool(data.get("needs_structure_review")),
        "parsed_json_payloads": json_payload_count,
        "jsonish_items": jsonish_count,
        "numbered_kv_items": numbered_kv_count,
        "heuristic_url_items": len(heuristic_rows),
        "evidence_count": len(evidence),
        "pending_count": len(pending),
        "prompt_drift": drift,
        "fallback_recommended": should_recommend_fallback(data, drift),
        "not_hit_games": not_hit_games,
        "source_file": str(path),
    }

    if False and data.get("status") == "error":
        pending.append(
            {
                "company": "平台状态",
                "game_name": str(data.get("ai_tool") or path.stem),
                "lead": f"平台采集失败：{data.get('error') or 'unknown_error'}",
                "reason": "platform_failure",
                "source_ai": data.get("ai_tool") or "",
                "source_file": str(path),
            }
        )
    elif False and drift:
        pending.append(
            {
                "company": "平台状态",
                "game_name": str(data.get("ai_tool") or path.stem),
                "lead": "疑似 prompt drift：AI 返回了自身产品/工具页面或未检索到游戏社区目标。",
                "reason": "prompt_drift",
                "source_ai": data.get("ai_tool") or "",
                "source_file": str(path),
            }
        )
    elif not evidence and not pending and response_text and should_surface_unparsed_pending(data, response_text):
        pending.append(
            {
                "company": "平台状态",
                "game_name": str(data.get("ai_tool") or path.stem),
                "lead": compact(response_text, 260),
                "reason": "unparsed_raw_text",
                "source_ai": data.get("ai_tool") or "",
                "source_file": str(path),
            }
        )
    return evidence, pending, status


def should_recommend_fallback(data: dict[str, Any], drift: bool) -> bool:
    tool = str(data.get("ai_tool") or "")
    if tool in {"千问", "Grok", "Gemini", "点点"}:
        return drift or data.get("status") == "error"
    return False


def dedupe_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        url = normalize_url(row.get("url"))
        key = url or "::".join(str(row.get(k) or "") for k in ["source_ai", "company", "game_name", "title", "summary"])[:240]
        if key in seen:
            continue
        seen.add(key)
        if url:
            row["url"] = url
        out.append(row)
    return out


def load_watch_games(game_list: str | None) -> list[dict[str, Any]]:
    if not game_list:
        return []
    path = Path(game_list)
    if not path.exists():
        return []
    records = read_spreadsheet(path)
    watch_games: list[dict[str, Any]] = []
    for record in records:
        aliases = [str(item).strip() for item in record.get("aliases", []) if str(item).strip()]
        if not aliases:
            continue
        watch_games.append(
            {
                "game_id": record.get("game_id", f"game_{len(watch_games) + 1:03d}"),
                "game_name": str(record.get("game_name") or aliases[0]).strip(),
                "aliases": aliases,
                "source_sheet": record.get("source_sheet", ""),
            }
        )
    return watch_games


def load_watch_games_from_prompt_pack(raw_files: list[Path]) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for raw_file in raw_files:
        raw_dir = raw_file.parent
        if raw_dir.name == "raw":
            candidates.append(raw_dir.parent / "prompt_pack.json")
        candidates.append(raw_dir / "prompt_pack.json")
    for pack_path in candidates:
        if not pack_path.exists():
            continue
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        records = pack.get("watch_games") or []
        watch_games: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            game_name = str(record.get("game_name") or record.get("name") or "").strip()
            aliases_raw = record.get("aliases") or []
            if isinstance(aliases_raw, str):
                aliases = [part.strip() for part in re.split(r"[/,;|，、]", aliases_raw) if part.strip()]
            else:
                aliases = [str(item).strip() for item in aliases_raw if str(item).strip()]
            if game_name and game_name not in aliases:
                aliases.insert(0, game_name)
            if not aliases:
                continue
            watch_games.append(
                {
                    "game_id": record.get("game_id", f"game_{len(watch_games) + 1:03d}"),
                    "game_name": game_name or aliases[0],
                    "aliases": aliases,
                    "source_sheet": record.get("source_sheet", "prompt_pack"),
                }
            )
        if watch_games:
            return watch_games
    return []


def matches_watch_game(row: dict[str, Any], game: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ["game_name", "matched_alias", "title", "summary", "plain_summary", "lead"]
    ).casefold()
    return any(str(alias).strip().casefold() in haystack for alias in game.get("aliases", []) if str(alias).strip())


def row_layer(row: dict[str, Any]) -> str:
    level = str(row.get("evidence_level") or "").strip()
    if row.get("url") and level == "core_evidence":
        return "core_evidence"
    if level == "auxiliary_sample":
        return "auxiliary_sample"
    return "pending_lead"


def is_non_key_company_item(row: dict[str, Any]) -> bool:
    if as_bool(row.get("is_key_company")):
        return False
    company = str(row.get("company") or "")
    category = str(row.get("category") or "")
    return not is_key_company_value(company) and any(marker in f"{company} {category}" for marker in ["二游大盘", "其他竞品", "竞品"])


def coverage_summary(
    evidence: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    watch_games: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = evidence + pending
    hit_games: list[dict[str, Any]] = []
    auxiliary_watch_games: list[dict[str, Any]] = []
    matched_game_ids: set[str] = set()
    for game in watch_games:
        matched_rows = [row for row in rows if matches_watch_game(row, game)]
        hit_count = len(matched_rows)
        if hit_count:
            matched_game_ids.add(str(game.get("game_id", "")))
            core_count = sum(1 for row in matched_rows if row_layer(row) == "core_evidence")
            auxiliary_count = sum(1 for row in matched_rows if row_layer(row) != "core_evidence")
            hit_games.append(
                {
                    "game_id": game.get("game_id", ""),
                    "game_name": game.get("game_name", ""),
                    "aliases": game.get("aliases", []),
                    "hit_count": hit_count,
                    "core_evidence_count": core_count,
                    "auxiliary_count": auxiliary_count,
                }
            )
            if auxiliary_count and not core_count:
                auxiliary_watch_games.append(hit_games[-1])
    unhit_watch_games = [
        {
            "game_id": game.get("game_id", ""),
            "game_name": game.get("game_name", ""),
            "aliases": game.get("aliases", []),
        }
        for game in watch_games
        if str(game.get("game_id", "")) not in matched_game_ids
    ]
    company_counter: dict[str, int] = {}
    for row in rows:
        company = str(row.get("company") or "其他").strip() or "其他"
        company_counter[company] = company_counter.get(company, 0) + 1
    source_counter: dict[str, dict[str, int]] = {}
    for row in rows:
        source_ai = str(row.get("source_ai") or "unknown").strip() or "unknown"
        bucket = source_counter.setdefault(source_ai, {"core_evidence": 0, "auxiliary_sample": 0, "pending_lead": 0})
        level = str(row.get("evidence_level") or ("core_evidence" if row.get("url") else "pending_lead"))
        if level not in bucket:
            level = "pending_lead"
        bucket[level] += 1
    sector_items = [row for row in rows if as_bool(row.get("sector_item")) or str(row.get("sector") or "").strip().casefold() not in {"", "none", "null", "n/a"}]
    non_key_company_items = [row for row in rows if is_non_key_company_item(row)]
    watch_matrix_coverage = {
        "watch_game_count": len(watch_games),
        "hit_watch_games": hit_games,
        "hit_watch_game_count": len(hit_games),
        "auxiliary_watch_games": auxiliary_watch_games,
        "auxiliary_watch_game_count": len(auxiliary_watch_games),
        "unhit_watch_games": unhit_watch_games,
        "unhit_watch_game_count": len(unhit_watch_games),
    }
    return {
        "watch_game_count": len(watch_games),
        "hit_games": hit_games,
        "hit_game_count": len(hit_games),
        "unhit_game_count": max(len(watch_games) - len(hit_games), 0),
        "watch_matrix_coverage": watch_matrix_coverage,
        "hit_watch_games": hit_games,
        "auxiliary_watch_games": auxiliary_watch_games,
        "unhit_watch_games": unhit_watch_games,
        "sector_items": sector_items,
        "sector_item_count": len(sector_items),
        "non_key_company_items": non_key_company_items,
        "non_key_company_item_count": len(non_key_company_items),
        "companies_hit_summary": company_counter,
        "source_layer_summary": {
            "by_source_ai": source_counter,
            "core_evidence": sum(1 for row in evidence if row.get("url")),
            "auxiliary_sample": sum(1 for row in pending if row_layer(row) == "auxiliary_sample"),
            "pending_leads": len(pending),
            "platform_status": len(statuses),
        },
    }


def source_ai_contribution_summary(
    evidence: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    raw_quality_audit: list[dict[str, Any]],
) -> dict[str, Any]:
    valid_ai = {
        str(row.get("ai_tool") or "").strip()
        for row in raw_quality_audit
        if row.get("valid_answer") and str(row.get("ai_tool") or "").strip()
    }
    summary: dict[str, dict[str, int]] = {}
    for row in evidence + pending:
        source_ai = str(row.get("source_ai") or "").strip()
        if not source_ai or source_ai not in valid_ai:
            continue
        bucket = summary.setdefault(source_ai, {"core_evidence": 0, "auxiliary_sample": 0, "pending_lead": 0, "total": 0})
        level = row_layer(row)
        bucket[level] = bucket.get(level, 0) + 1
        bucket["total"] += 1
    contributing_ai = sorted(name for name, counts in summary.items() if counts.get("total", 0) > 0)
    return {
        "contributing_ai_count": len(contributing_ai),
        "contributing_ai": contributing_ai,
        "source_ai_contribution_summary": summary,
    }


def annotate_watch_matrix(rows: list[dict[str, Any]], watch_games: list[dict[str, Any]]) -> None:
    if not watch_games:
        return
    for row in rows:
        for game in watch_games:
            if matches_watch_game(row, game):
                row["is_watch_matrix_game"] = True
                row.setdefault("watch_game_id", game.get("game_id", ""))
                if not row.get("matched_alias"):
                    row["matched_alias"] = str(game.get("game_name") or "")
                break


def aggregate_not_hit_games(statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for status in statuses:
        for item in status.get("not_hit_games") or []:
            game_name = compact(item.get("game_name") or "", 120)
            reason = compact(item.get("not_hit_reason") or item.get("reason") or "", 260)
            if not game_name and not reason:
                continue
            key = (game_name.casefold(), reason.casefold())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "game_name": game_name,
                    "matched_alias": compact(item.get("matched_alias") or "", 160),
                    "not_hit_reason": reason or "本周期没有找到具体公开信息/社区讨论。",
                    "source_ai": item.get("source_ai") or status.get("ai_tool") or "",
                    "source_file": item.get("source_file") or status.get("source_file") or "",
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Raw Web AI JSON files or directories")
    parser.add_argument("--output", required=True, help="Structured JSON output path")
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--report-mode", choices=["daily", "weekly"], default="weekly")
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--game-list", default="", help="Optional watch matrix used for coverage statistics.")
    args = parser.parse_args()

    evidence: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    raw_files = collect_files(args.inputs)
    raw_quality_audit = [audit_file(path) for path in raw_files]
    raw_quality_summary = summarize_audit(raw_quality_audit)
    raw_quality_by_file = {str(row.get("source_file") or ""): row for row in raw_quality_audit}

    for path in raw_files:
        try:
            rows, leads, status = structure_file(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        audit_row = raw_quality_by_file.get(str(path)) or raw_quality_by_file.get(str(path.resolve()))
        if audit_row:
            status["raw_quality_valid_answer"] = bool(audit_row.get("valid_answer"))
            status["raw_quality_answer_quality"] = audit_row.get("answer_quality") or ""
            status["raw_quality_invalid_reason"] = audit_row.get("invalid_reason") or ""
            status["raw_quality_capture_mode"] = audit_row.get("capture_mode") or ""
            status["raw_quality_needs_human_review"] = bool(audit_row.get("needs_human_review"))
        if audit_row and not audit_row.get("valid_answer"):
            status["evidence_count"] = 0
            status["pending_count"] = 0
            status["raw_quality_gate"] = "blocked_invalid_answer"
            statuses.append(status)
            continue
        evidence.extend(rows)
        pending.extend(leads)
        statuses.append(status)
    final_evidence = dedupe_evidence(evidence)
    final_pending = [normalize_structured_row(row, target="pending") for row in pending]
    watch_games = load_watch_games(args.game_list) or load_watch_games_from_prompt_pack(raw_files)
    annotate_watch_matrix(final_evidence, watch_games)
    annotate_watch_matrix(final_pending, watch_games)
    coverage = coverage_summary(final_evidence, final_pending, statuses, watch_games)
    contribution = source_ai_contribution_summary(final_evidence, final_pending, raw_quality_audit)
    coverage["source_ai_contribution_summary"] = contribution["source_ai_contribution_summary"]
    coverage["contributing_ai_count"] = contribution["contributing_ai_count"]
    coverage["contributing_ai"] = contribution["contributing_ai"]
    not_hit_games = aggregate_not_hit_games(statuses)

    payload = {
        "ai_tool": "robust_local_structurer",
        "report_mode": args.report_mode,
        "report_window": {
            "end_date": args.report_date,
            "lookback_days": args.lookback_days,
        },
        "coverage_summary": coverage,
        "watch_game_count": coverage["watch_game_count"],
        "hit_games": coverage["hit_games"],
        "hit_game_count": coverage["hit_game_count"],
        "unhit_game_count": coverage["unhit_game_count"],
        "watch_matrix_coverage": coverage["watch_matrix_coverage"],
        "hit_watch_games": coverage["hit_watch_games"],
        "auxiliary_watch_games": coverage["auxiliary_watch_games"],
        "unhit_watch_games": coverage["unhit_watch_games"],
        "sector_items": coverage["sector_items"],
        "sector_item_count": coverage["sector_item_count"],
        "non_key_company_items": coverage["non_key_company_items"],
        "non_key_company_item_count": coverage["non_key_company_item_count"],
        "not_hit_games": not_hit_games,
        "companies_hit_summary": coverage["companies_hit_summary"],
        "source_layer_summary": coverage["source_layer_summary"],
        "contributing_ai_count": contribution["contributing_ai_count"],
        "contributing_ai": contribution["contributing_ai"],
        "source_ai_contribution_summary": contribution["source_ai_contribution_summary"],
        "raw_quality_audit": raw_quality_audit,
        "valid_answer_count": raw_quality_summary["valid_answer_count"],
        "invalid_answer_count": raw_quality_summary["invalid_answer_count"],
        "valid_answer_by_ai": raw_quality_summary["valid_answer_by_ai"],
        "evidence": final_evidence,
        "pending_leads": final_pending,
        "platform_status": statuses,
        "errors": errors,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_audit_outputs(raw_quality_audit, output.parent)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "evidence": len(payload["evidence"]),
                "pending_leads": len(payload["pending_leads"]),
                "watch_game_count": payload["watch_game_count"],
                "hit_game_count": payload["hit_game_count"],
                "unhit_game_count": payload["unhit_game_count"],
                "valid_answer_count": payload["valid_answer_count"],
                "invalid_answer_count": payload["invalid_answer_count"],
                "contributing_ai_count": payload["contributing_ai_count"],
                "platform_status": len(statuses),
                "errors": len(errors),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
