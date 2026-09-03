#!/usr/bin/env python3
"""Render a dark executive dashboard for company/market daily intelligence."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PRODUCTS: list[dict[str, str]] = [
    {"company": "米哈游", "game_name": "FlyMe2theMoon", "aliases": "FlyMe2theMoon", "product_tier": "history_context", "game_status": "早期独立游戏，历史产品"},
    {"company": "米哈游", "game_name": "崩坏学园", "aliases": "Zombiegal Kawaii; Houkai Gakuen", "product_tier": "history_context", "game_status": "早期历史产品"},
    {"company": "米哈游", "game_name": "崩坏学园2", "aliases": "Houkai Gakuen 2", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "崩坏3", "aliases": "Honkai Impact 3rd", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "未定事件簿", "aliases": "Tears of Themis", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "原神", "aliases": "Genshin Impact", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "崩坏：星穹铁道", "aliases": "Honkai: Star Rail; HSR", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "绝区零", "aliases": "Zenless Zone Zero; ZZZ", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "米哈游", "game_name": "崩坏：因缘精灵", "aliases": "Honkai: Nexus Anima", "product_tier": "research_watch", "game_status": "正在进行“进化测试”"},
    {"company": "米哈游", "game_name": "星布谷地", "aliases": "Petit Planet", "product_tier": "research_watch", "game_status": "已完成多轮封闭测试，继续研发和预约"},
    {"company": "米哈游", "game_name": "Varsapura", "aliases": "雨之城", "product_tier": "research_watch", "game_status": "已开启首轮保密测试招募"},
    {"company": "库洛", "game_name": "鸣潮", "aliases": "Wuthering Waves; WuWa", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
    {"company": "库洛", "game_name": "战双帕弥什", "aliases": "Punishing: Gray Raven; PGR", "product_tier": "daily_focus", "game_status": "已上线、持续运营"},
]

BLOCKED_STATUSES = {"blocked_login", "forbidden_403", "captcha", "paywalled", "no_url"}


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def normalize_url(url: Any) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    lowered = value.casefold()
    if (
        "如有真实" in value
        or "没有就留空" in value
        or "https://..." in value
        or any(marker in lowered for marker in ["示例", "样例", "placeholder", "example url"])
    ):
        return ""
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return ""
    if parts.scheme.lower() not in {"http", "https"}:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_") and k not in {"spm", "from", "source"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def canonical_company_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    folded = text.casefold()
    if "米哈游" in text or "mihoyo" in folded or "hoyoverse" in folded:
        return "米哈游"
    if "库洛" in text or "kuro" in folded:
        return "库洛"
    if "二游大盘" in text or text == "大盘" or "market" in folded:
        return "二游大盘"
    return text


def is_placeholder_record(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ["company", "game_name", "title", "url", "published_at", "summary", "risk_level", "sentiment"]
    )
    markers = [
        "米哈游 | 库洛 | 二游大盘",
        "游戏名；大盘趋势可填",
        "帖子/视频/问答/新闻/公告标题",
        "YYYY-MM-DD",
        "https://...",
        "如有真实",
        "没有就留空",
        "accessible/no_url/search_snippet_only",
        "版本/角色/剧情/玩法/付费/运营/争议/玩家建议/大盘趋势",
        "入坑/回流/退坑/抽卡/付费/观望/建议/分化",
        "low | medium | high",
        "positive | negative | neutral | mixed",
        "low/medium/high",
        "positive/negative/neutral/mixed",
    ]
    return any(marker in text for marker in markers) or is_raw_json_fragment_record(row)


def is_raw_json_fragment_record(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ["title", "summary", "specific_player_opinions", "why_watch"])
    json_markers = [
        '"company":',
        '"game_name":',
        '"matched_alias":',
        '"product_tier":',
        '"source_ai":',
        '"source_file":',
        '"url":',
        "'company':",
        "'game_name':",
        "'matched_alias':",
        "'product_tier':",
        "'source_ai':",
        "'source_file':",
        "'url':",
    ]
    if sum(1 for marker in json_markers if marker in text) >= 2:
        return True
    stripped = text.strip()
    return stripped.startswith(('"company":', '{"company":', '"game_name":', '{"game_name":', "'company':", "{'company':", "'game_name':", "{'game_name':"))


def is_ai_tool_prompt_drift(row: dict[str, Any], source_ai: Any = "") -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ["company", "game_name", "title", "url", "lead", "summary", "reason", "limitations"]
    ).casefold()
    ai_name = str(source_ai or row.get("source_ai") or row.get("ai_tool") or "").casefold()
    url = str(row.get("url") or "").casefold()
    qianwen_markers = ["千问", "qwen", "通义千问", "阿里 ai 助手", "阿里ai助手"]
    product_markers = ["官网", "产品介绍", "产品功能", "功能介绍", "api 服务", "api服务", "下载", "ai助手官网", "助手官网"]
    failed_search_markers = ["未发现", "没有发现", "无相关", "仅返回", "只返回", "没有与游戏"]
    if "qianwen" in url and not any(game in text for game in ["原神", "星穹", "绝区零", "鸣潮", "战双", "米哈游", "库洛"]):
        return True
    if "千问" in ai_name or "qianwen" in ai_name:
        has_tool = any(marker in text for marker in qianwen_markers)
        has_product = any(marker in text for marker in product_markers)
        has_failed = any(marker in text for marker in failed_search_markers)
        if has_tool and (has_product or has_failed):
            return True
    return False


def product_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for item in PRODUCTS:
        aliases = [alias.strip() for alias in item["aliases"].split(";") if alias.strip()]
        for name in [item["game_name"], *aliases]:
            lookup[name.casefold()] = item
    return lookup


PRODUCT_BY_NAME = product_lookup()


def infer_product(game_name: str, matched_alias: str = "") -> dict[str, str]:
    for value in (game_name, matched_alias):
        key = str(value or "").strip().casefold()
        if key in PRODUCT_BY_NAME:
            return PRODUCT_BY_NAME[key]
    text = f"{game_name} {matched_alias}".casefold()
    for key, item in PRODUCT_BY_NAME.items():
        if key and key in text:
            return item
    return {}


def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def parse_json_from_text(text: str) -> Any | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    candidates = [raw]
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if match:
        candidates.insert(0, match.group(1).strip())
    first, last = raw.find("{"), raw.rfind("}")
    if first != -1 and last > first:
        candidates.append(raw[first : last + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def load_json_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except Exception:
        parsed = parse_json_from_text(text)
        if parsed is not None:
            return parsed
        raise


def containers_from_data(data: Any) -> list[dict[str, Any]]:
    raw_items = data if isinstance(data, list) else [data]
    containers: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        containers.append(item)
        if not (item.get("evidence") or item.get("items") or item.get("records")) and item.get("response_text"):
            parsed = parse_json_from_text(str(item.get("response_text")))
            if isinstance(parsed, dict):
                merged = dict(parsed)
                merged.setdefault("ai_tool", item.get("ai_tool"))
                merged.setdefault("prompt_id", item.get("prompt_id"))
                containers.append(merged)
    return containers


def evidence_level(url: str, access_status: str) -> str:
    if not url:
        return "secondary_only"
    if access_status in BLOCKED_STATUSES:
        return "excluded"
    return "core" if access_status in {"accessible", "unknown", ""} else "supporting"


def normalize_record(item: dict[str, Any], source: dict[str, Any], source_file: Path) -> dict[str, Any]:
    url = normalize_url(item.get("url") or item.get("link") or "")
    game_name = str(item.get("game_name") or item.get("game") or "").strip()
    matched_alias = str(item.get("matched_alias") or item.get("alias_matched") or "").strip()
    inferred = infer_product(game_name, matched_alias)
    if not inferred:
        inferred = infer_product(
            " ".join(
                str(item.get(field) or "")
                for field in ["game_name", "matched_alias", "title", "summary", "plain_summary"]
            ),
            "",
        )
    company = str(item.get("company") or inferred.get("company") or source.get("company") or "").strip()
    if inferred.get("company") and canonical_company_name(company) in {"", "二游大盘", "其他"}:
        company = inferred["company"]
    if not company and (game_name in {"二游大盘", "大盘"} or item.get("scope") == "market"):
        company = "二游大盘"
    if not company:
        company = "其他"
    company = canonical_company_name(company)
    if inferred.get("game_name") and company in {"米哈游", "库洛"}:
        game_name = inferred["game_name"]
    if not game_name:
        game_name = "二游大盘" if company == "二游大盘" else inferred.get("game_name", "")
    access_status = str(item.get("access_status") or ("unknown" if url else "no_url")).strip()
    level = item.get("evidence_level") or evidence_level(url, access_status)
    return {
        "company": company,
        "category": item.get("category") or "",
        "game_name": game_name or company,
        "matched_alias": matched_alias,
        "product_tier": item.get("product_tier") or inferred.get("product_tier") or ("market" if company == "二游大盘" else ""),
        "game_status": item.get("game_status") or inferred.get("game_status") or ("大盘" if company == "二游大盘" else ""),
        "scope": item.get("scope") or ("market" if company == "二游大盘" else "game"),
        "platform": item.get("platform") or item.get("source_platform") or source.get("platform_focus") or "",
        "source_ai": item.get("source_ai") or source.get("ai_tool") or source.get("source_ai") or "",
        "title": item.get("title") or item.get("event_or_discussion") or item.get("summary") or url,
        "url": url,
        "published_at": item.get("published_at") or "",
        "retrieved_at": item.get("retrieved_at") or source.get("retrieved_at") or date.today().isoformat(),
        "event_type": item.get("event_type") or item.get("topic") or "其他",
        "player_tendency": item.get("player_tendency") or item.get("player_intent") or "",
        "player_intent": item.get("player_intent") or "",
        "sentiment": item.get("sentiment") or item.get("player_sentiment") or "",
        "risk_level": str(item.get("risk_level") or "low").lower(),
        "summary": item.get("summary") or item.get("event_summary") or "",
        "plain_summary": item.get("plain_summary") or item.get("summary") or item.get("event_summary") or item.get("title") or "",
        "specific_player_opinions": item.get("specific_player_opinions") or item.get("player_opinions") or item.get("snippet") or "",
        "why_watch": item.get("why_watch") or item.get("evidence_support") or "",
        "business_use": item.get("business_use") or item.get("why_watch") or item.get("summary") or "",
        # Keep the internal no-sector marker in structured data, but never leak
        # the literal placeholder into the reader-facing report.
        "sector": "" if str(item.get("sector") or "").strip().casefold() in {"none", "null", "n/a", "无"} else item.get("sector") or "",
        "sector_item": item.get("sector_item") or False,
        "is_watch_matrix_game": item.get("is_watch_matrix_game") or False,
        "is_key_company": item.get("is_key_company") or company in {"米哈游", "库洛"},
        "access_status": access_status,
        "evidence_level": level,
        "limitations": item.get("limitations") or "",
        "source_file": str(source_file),
    }


def merge_report_metadata(container: dict[str, Any], metadata: dict[str, Any]) -> None:
    for key in [
        "watch_game_count",
        "hit_games",
        "hit_game_count",
        "unhit_game_count",
        "report_mode",
        "watch_matrix_coverage",
        "hit_watch_games",
        "auxiliary_watch_games",
        "unhit_watch_games",
        "sector_items",
        "sector_item_count",
        "non_key_company_items",
        "non_key_company_item_count",
        "not_hit_games",
        "companies_hit_summary",
        "source_layer_summary",
        "raw_quality_audit",
        "valid_answer_count",
        "invalid_answer_count",
        "valid_answer_by_ai",
        "contributing_ai_count",
        "contributing_ai",
        "source_ai_contribution_summary",
    ]:
        value = container.get(key)
        if key in container and value is not None and value != "":
            metadata[key] = value


def load_outputs(files: list[Path], allow_no_url_evidence: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[dict[str, Any]], dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    errors: list[str] = []
    platform_status: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    for path in files:
        try:
            data = load_json_file(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            platform_status.append(
                {
                    "prompt_id": path.stem,
                    "ai_tool": "",
                    "status": "parse_error",
                    "error": str(exc),
                    "source_file": str(path),
                }
            )
            continue
        for container in containers_from_data(data):
            merge_report_metadata(container, metadata)
            source_ai = container.get("ai_tool") or container.get("source_ai") or ""
            for status_item in as_list(container.get("platform_status")):
                if isinstance(status_item, dict):
                    row = dict(status_item)
                    row.setdefault("source_file", str(path))
                    platform_status.append(row)
            if container.get("status") or container.get("error") or container.get("parsed_json") is not None:
                platform_status.append(
                    {
                        "prompt_id": container.get("prompt_id") or path.stem,
                        "ai_tool": source_ai,
                        "status": container.get("status") or "unknown",
                        "error": container.get("error") or "",
                        "parsed_json": container.get("parsed_json"),
                        "prompt_drift": container.get("prompt_drift", False),
                        "source_file": str(path),
                    }
                )
            for lead in as_list(container.get("pending_leads")):
                row = dict(lead) if isinstance(lead, dict) else {"lead": str(lead)}
                row.setdefault("source_ai", source_ai)
                row.setdefault("source_file", str(path))
                if is_ai_tool_prompt_drift(row, source_ai):
                    errors.append(f"{path}: prompt_drift:{source_ai}: {str(row.get('lead') or row.get('title') or '')[:120]}")
                    continue
                pending.append(row)
            for raw_item in as_list(container.get("evidence") or container.get("items") or container.get("records")):
                if not isinstance(raw_item, dict):
                    continue
                row = normalize_record(raw_item, container, path)
                if is_placeholder_record(row):
                    continue
                if is_ai_tool_prompt_drift(row, row.get("source_ai")):
                    errors.append(f"{path}: prompt_drift:{row.get('source_ai')}: {str(row.get('summary') or row.get('title') or '')[:120]}")
                    continue
                if not row["url"] and allow_no_url_evidence:
                    row["evidence_id"] = f"ev_{len(seen) + 1:04d}"
                    row["evidence_level"] = "auxiliary_sample"
                    row["access_status"] = row.get("access_status") or "no_url"
                    row["limitations"] = row.get("limitations") or "No URL in this relaxed sampling run; verify before external use."
                    key = f"no_url::{row.get('company')}::{row.get('game_name')}::{row.get('title')}::{len(seen)}"
                    seen[key] = row
                    continue
                if not row["url"]:
                    pending.append(
                        {
                            "company": row["company"],
                            "game_name": row["game_name"],
                            "source_ai": row["source_ai"],
                            "lead": row["summary"] or row["title"],
                            "reason": "no_url",
                            "source_file": str(path),
                        }
                    )
                    continue
                key = row["url"]
                if key not in seen:
                    row["evidence_id"] = f"ev_{len(seen) + 1:04d}"
                    seen[key] = row
    status_seen: set[tuple[str, str, str]] = set()
    deduped_status: list[dict[str, Any]] = []
    for item in platform_status:
        key = (str(item.get("prompt_id") or ""), str(item.get("ai_tool") or ""), str(item.get("source_file") or ""))
        if key in status_seen:
            continue
        status_seen.add(key)
        deduped_status.append(item)
    return list(seen.values()), pending, list(dict.fromkeys(errors)), deduped_status, metadata


def risk_rank(value: str) -> int:
    text = str(value or "").strip().lower()
    if text in {"high", "高", "高风险"}:
        return 3
    if text in {"medium", "mid", "中", "中风险", "中等"}:
        return 2
    if text in {"low", "低", "低风险"}:
        return 1
    return 0


def risk_text(value: str) -> str:
    rank = risk_rank(value)
    return {3: "高风险", 2: "中风险", 1: "低风险"}.get(rank, value or "低风险")


def risk_class(value: str) -> str:
    return {3: "risk-high", 2: "risk-medium", 1: "risk-low"}.get(risk_rank(value), "risk-low")


def tier_label(value: str) -> str:
    return {
        "daily_focus": "日常重点",
        "research_watch": "研发/测试观察",
        "history_context": "历史/品牌线索",
        "market": "二游大盘",
    }.get(value or "", value or "未标注")


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def health_score(records: list[dict[str, Any]]) -> int:
    high = sum(1 for item in records if risk_rank(item.get("risk_level", "")) == 3)
    medium = sum(1 for item in records if risk_rank(item.get("risk_level", "")) == 2)
    positive = sum(1 for item in records if item.get("sentiment") == "positive")
    return clamp(82 + positive * 2 - high * 16 - medium * 7)


def date_labels(report_date: str, lookback_days: int) -> list[str]:
    end = date.fromisoformat(report_date)
    return [(end - timedelta(days=lookback_days - offset - 1)).isoformat() for offset in range(lookback_days)]


def record_date(item: dict[str, Any], fallback: str) -> str:
    text = " ".join(str(item.get(key) or "") for key in ["published_at", "retrieved_at"])
    match = re.search(r"20\d{2}-\d{2}-\d{2}", text)
    return match.group(0) if match else fallback


def chart_payload(records: list[dict[str, Any]], report_date: str, lookback_days: int) -> dict[str, Any]:
    labels = date_labels(report_date, lookback_days)
    total = Counter()
    positive = Counter()
    negative = Counter()
    for item in records:
        day = record_date(item, labels[-1])
        if day not in labels:
            day = labels[-1]
        total[day] += 1
        if item.get("sentiment") == "positive":
            positive[day] += 1
        if item.get("sentiment") == "negative" or item.get("risk_level") == "high":
            negative[day] += 1
    return {
        "labels": labels,
        "total": [total[day] for day in labels],
        "positive": [positive[day] for day in labels],
        "negative": [negative[day] for day in labels],
    }


def counter_text(counter: Counter[str], empty: str = "暂无") -> str:
    return "、".join(f"{key}:{value}" for key, value in counter.most_common() if key) or empty


def company_records(records: list[dict[str, Any]], company: str) -> list[dict[str, Any]]:
    canonical = canonical_company_name(company)
    return [item for item in records if canonical_company_name(item.get("company")) == canonical]


def evidence_link(item: dict[str, Any], label: str = "\u67e5\u770b\u94fe\u63a5") -> str:
    url = str(item.get("url") or "").strip()
    if url:
        return f"<a class='evidence-link' href='{esc(url)}' target='_blank' rel='noreferrer'>{esc(label)}</a>"
    verification = platform_verification_link(item)
    if verification:
        verify_label, verify_url, verify_class = verification
        return f"<a class='evidence-link verify-link {esc(verify_class)}' href='{esc(verify_url)}' target='_blank' rel='noreferrer'>{esc(verify_label)}</a>"
    return "<span class='aux-link'>辅助样本</span>"


def compact_text(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


DISPLAY_TRANSLATIONS: list[tuple[str, str]] = [
    ("Honkai: Star Rail × Fate[UBW] Collab Trailer — \"A Long Awaited Reunion\"", "《崩坏：星穹铁道》× Fate[UBW] 联动预告：「久候的重逢」"),
    ("Honkai: Star Rail x Fate[UBW] Collab Trailer - \"A Long Awaited Reunion\"", "《崩坏：星穹铁道》× Fate[UBW] 联动预告：「久候的重逢」"),
    ("Honkai: Star Rail × Fate[UBW] Collab Trailer", "《崩坏：星穹铁道》× Fate[UBW] 联动预告"),
    ("Honkai: Star Rail x Fate[UBW] Collab Trailer", "《崩坏：星穹铁道》× Fate[UBW] 联动预告"),
    ("A Long Awaited Reunion", "久候的重逢"),
    ("Honkai Star Rail Next Update And Banners", "《崩坏：星穹铁道》后续更新与卡池"),
    ("Honkai: Star Rail Next Update And Banners", "《崩坏：星穹铁道》后续更新与卡池"),
    ("HoYoverse reveals Gamescom 2026 lineup", "HoYoverse 公布 Gamescom 2026 参展阵容"),
    ("Post-Lament Anthropocene: Stars Intertwined | Suisui", "《鸣潮》岁岁角色前瞻：星辉交织"),
    ("Wuthering Waves Resonator Combat Showcase | Suisui", "《鸣潮》共鸣者岁岁战斗展示"),
    ("Wuthering Waves", "鸣潮"),
    ("Zenless Zone Zero", "绝区零"),
    ("ZZZ Version 3.1: Free S-Rank Agent Selector & More", "《绝区零》3.1 版本：免费 S 级代理人自选等内容"),
    ("ZZZ's Free S-Rank Selector Has Players Recommending One Agent Above All Else", "《绝区零》免费 S 级自选引发玩家集中推荐"),
    ("Genshin Impact", "原神"),
    ("Honkai: Star Rail", "崩坏：星穹铁道"),
    ("Honkai Star Rail", "崩坏：星穹铁道"),
    ("Honkai Impact 3rd", "崩坏3"),
    ("Honkai: Nexus Anima", "崩坏：因缘精灵"),
    ("Punishing: Gray Raven", "战双帕弥什"),
    ("Tears of Themis", "未定事件簿"),
    ("Petit Planet", "星布谷地"),
    ("Free S-Rank Agent Selector", "免费 S 级代理人自选"),
    ("Free S-Rank Selector", "免费 S 级自选"),
    ("S-Rank Agent Selector", "S 级代理人自选"),
    ("Combat Showcase", "战斗展示"),
    ("Collab Trailer", "联动预告"),
    ("Next Update And Banners", "后续更新与卡池"),
    ("Players Recommending", "玩家推荐"),
    ("Platform Gemini collection failed: user_message_not_confirmed", "Gemini 用户消息发送未确认"),
    ("user_message_not_confirmed", "用户消息发送未确认"),
    ("prompt drift", "提示词漂移"),
    ("source_file", "来源文件"),
    ("Official", "官方"),
    ("official", "官方"),
    ("News", "新闻"),
    ("news", "新闻"),
]


STATUS_ONLY_MARKERS = [
    "Platform Gemini collection failed",
    "user_message_not_confirmed",
    "平台采集失败",
    "发送未确认",
    "prompt drift",
    "daily_ai_outputs\\",
]


def looks_like_raw_json_fragment(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    markers = ['"company":', '"game_name":', '"source_ai":', '"source_file":', "'company':", "'game_name':", "'source_ai':", "'source_file':"]
    if sum(1 for marker in markers if marker in text) >= 2:
        return True
    return text.startswith(("{'company':", '{"company":', "'company':", '"company":'))


def is_status_only_text(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in STATUS_ONLY_MARKERS)


def display_text(value: Any) -> str:
    text = compact_text(value, 260)
    if looks_like_raw_json_fragment(text):
        return ""
    for source, target in DISPLAY_TRANSLATIONS:
        text = text.replace(source, target)
    text = re.sub(r"\bZZZ\b", "绝区零", text)
    text = re.sub(r"\bHSR\b", "星铁", text)
    text = re.sub(r"\bWuWa\b", "鸣潮", text)
    text = re.sub(r"\bPGR\b", "战双", text)
    text = text.replace("X/Twitter", "X/Twitter")
    return text.strip()


def display_compact(value: Any, limit: int = 120, fallback: str = "") -> str:
    text = display_text(value)
    if not text:
        return fallback
    return compact_text(text, limit)


def display_platform(value: Any) -> str:
    text = display_text(value)
    return {
        "Official": "官方",
        "official": "官方",
        "News": "新闻",
        "news": "新闻",
        "X": "X",
    }.get(text, text or "未知平台")


def platform_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in [
            "platform",
            "source_ai",
            "source_url",
            "source_title",
            "limitations",
            "title",
            "lead",
            "summary",
            "reason",
        ]
    ).casefold()


def platform_search_query(item: dict[str, Any]) -> str:
    pieces = [
        str(item.get("game_name") or "").replace("/", " "),
        str(item.get("title") or ""),
        str(item.get("lead") or ""),
        str(item.get("summary") or ""),
        str(item.get("event_type") or ""),
        str(item.get("platform") or ""),
    ]
    query = re.sub(r"\s+", " ", " ".join(piece for piece in pieces if piece).strip())
    return query[:90] or "二次元游戏 舆情"


def platform_verification_link(item: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return a public search link for URL-less leads; this is a manual verification aid."""
    query = platform_search_query(item)
    text = platform_text(item)
    if not query:
        return None
    if any(marker in text for marker in ["小红书", "点点", "xiaohongshu", "xhs", "rednote"]):
        url = "https://www.xiaohongshu.com/search_result?" + urlencode(
            {"keyword": query, "source": "web_explore_feed"}
        )
        return "小红书核验", url, "xhs-verify"
    if any(marker in text for marker in ["百度贴吧", "贴吧", "tieba.baidu", "tieba"]):
        url = "https://tieba.baidu.com/f/search/res?" + urlencode({"ie": "utf-8", "qw": query})
        return "贴吧核验", url, "tieba-verify"
    if any(marker in text for marker in ["b站", "哔哩", "bilibili", "b23.tv"]):
        url = "https://search.bilibili.com/all?" + urlencode({"keyword": query})
        return "B站核验", url, "bili-verify"
    if any(marker in text for marker in ["微博", "weibo"]):
        url = "https://s.weibo.com/weibo?" + urlencode({"q": query})
        return "微博核验", url, "weibo-verify"
    if any(marker in text for marker in ["知乎", "zhihu", "知乎直答"]):
        url = "https://www.zhihu.com/search?" + urlencode({"type": "content", "q": query})
        return "知乎核验", url, "zhihu-verify"
    if "taptap" in text:
        url = "https://www.taptap.cn/search?" + urlencode({"keyword": query})
        return "TapTap核验", url, "taptap-verify"
    if any(marker in text for marker in ["nga", "ngabbs"]):
        url = "https://www.baidu.com/s?" + urlencode({"wd": f"site:ngabbs.com/read.php {query}"})
        return "NGA核验", url, "generic-verify"
    if any(marker in text for marker in ["百度", "baidu", "中文网页", "全网", "新闻", "论坛", "文心", "元宝", "豆包"]):
        url = "https://www.baidu.com/s?" + urlencode({"wd": query})
        return "公开搜索核验", url, "generic-verify"
    return None


def is_xhs_record(item: dict[str, Any]) -> bool:
    text = " ".join(
        str(item.get(key) or "")
        for key in ["platform", "source_ai", "source_url", "limitations", "source_title"]
    ).casefold()
    return "小红书" in text or "点点" in text or "xiaohongshu" in text or "xhs" in text


def xhs_search_query(item: dict[str, Any]) -> str:
    pieces = [
        str(item.get("game_name") or "").replace("/", " "),
        str(item.get("title") or ""),
        str(item.get("event_type") or ""),
    ]
    query = re.sub(r"\s+", " ", " ".join(piece for piece in pieces if piece).strip())
    return query[:80] or "二次元游戏 舆情"


def xhs_search_url(item: dict[str, Any]) -> str:
    return "https://www.xiaohongshu.com/search_result?" + urlencode(
        {"keyword": xhs_search_query(item), "source": "web_explore_feed"}
    )


def tag_cloud(records: list[dict[str, Any]], limit: int = 12) -> str:
    words = Counter()
    for item in records:
        for field in ["game_name", "event_type", "player_tendency", "player_intent"]:
            value = display_text(item.get(field))
            if value:
                words[value] += 1
    if not words:
        return "<span class='tag'>暂无高频标签</span>"
    return "".join(f"<span class='tag'>{esc(display_text(word))}</span>" for word, _ in words.most_common(limit))


def kpi_delta(records: list[dict[str, Any]]) -> str:
    high = sum(1 for item in records if item.get("risk_level") == "high")
    if high:
        return f"风险 +{high}"
    if records:
        return "样本活跃"
    return "待采集"


CONTENT_GROUPS: list[tuple[str, str, str]] = [
    ("community", "社区讨论", "messages-square"),
    ("version", "版本更新", "calendar-days"),
    ("news", "新闻公告", "newspaper"),
]


def content_group(item: dict[str, Any]) -> str:
    text = " ".join(
        display_text(item.get(key))
        for key in ["platform", "source_ai", "title", "summary", "event_type", "specific_player_opinions", "why_watch"]
    ).casefold()
    raw = " ".join(str(item.get(key) or "") for key in ["url", "platform", "source_ai", "source_file"]).casefold()
    community_markers = [
        "小红书",
        "知乎",
        "贴吧",
        "b站",
        "哔哩",
        "微博",
        "nga",
        "taptap",
        "x/twitter",
        "twitter",
        "reddit",
        "论坛",
        "社区",
        "点点",
        "zhihu",
        "weibo",
        "bilibili",
        "xiaohongshu",
        "tieba",
    ]
    version_markers = [
        "版本",
        "更新",
        "前瞻",
        "卡池",
        "活动",
        "周年",
        "联动",
        "角色",
        "pv",
        "预告",
        "上线",
        "测试",
        "招募",
        "自选",
        "直播",
        "公告",
        "限时",
        "s级",
        "s 级",
    ]
    news_markers = [
        "新闻",
        "媒体",
        "gamespot",
        "ign",
        "mmos",
        "notebookcheck",
        "game8",
        "展会",
        "gamescom",
        "报道",
        "news",
    ]
    if any(marker in text or marker in raw for marker in community_markers):
        return "community"
    if any(marker in text for marker in version_markers):
        return "version"
    if any(marker in text or marker in raw for marker in news_markers):
        return "news"
    return "news"


def company_event_card(item: dict[str, Any]) -> str:
    title = display_compact(item.get("title") or item.get("summary"), 120, "未命名事件")
    title_node = (
        f"<a class='event-title' href='{esc(item.get('url'))}' target='_blank' rel='noreferrer'>{esc(title)}</a>"
        if item.get("url")
        else f"<span class='event-title'>{esc(title)}</span>"
    )
    opinions = compact_content(item.get("specific_player_opinions"), 150)
    why_watch = compact_content(item.get("why_watch"), 120)
    plain_summary = compact_content(item.get("plain_summary") or item.get("summary") or item.get("title"), 180) or title
    business_use = compact_content(item.get("business_use"), 120)
    level_badge = evidence_badge(item.get("evidence_level"), bool(item.get("url")))
    action_link = evidence_link(item)
    if not item.get("url"):
        verification = platform_verification_link(item)
        if verification:
            verify_label, verify_url, verify_class = verification
            action_link = f"<a class='evidence-link verify-link {esc(verify_class)}' href='{esc(verify_url)}' target='_blank' rel='noreferrer'>{esc(verify_label)}</a>"
    fields = [
        ("大白话说明", plain_summary, "event-summary"),
        ("玩家反馈", opinions, "event-opinion"),
        ("为什么值得关注", why_watch, "event-watch"),
        ("业务使用", business_use, "event-business"),
    ]
    field_html = "".join(
        f"<div class='event-field {esc(css_class)}'><span>{esc(label)}</span><p>{esc(text)}</p></div>"
        for label, text, css_class in fields
        if text
    )
    return f"""
      <article class="company-event">
        <div class="event-meta">
          <span>{esc(display_text(item.get('game_name')))}</span>
          <span>{esc(display_platform(item.get('platform')))}</span>
          {level_badge}
          <span class="risk-pill {risk_class(item.get('risk_level'))}">{esc(risk_text(item.get('risk_level')))}</span>
        </div>
        {title_node}
        <div class="event-fields">{field_html}</div>
        <footer><span>{esc(item.get('published_at') or item.get('retrieved_at'))}</span>{action_link}</footer>
      </article>
    """


def company_focus_card(company: str, records: list[dict[str, Any]], accent_class: str) -> str:
    rows = [item for item in company_records(records, company) if not is_raw_json_fragment_record(item)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        game_label = display_text(item.get("game_name")) or company
        grouped[game_label].append(item)
    hit_games = "".join(
        f"<span class='focus-game'>{esc(game)}<b>{len(items)}</b></span>"
        for game, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:8]
    ) or "<span class='focus-game'>暂无命中<b>0</b></span>"
    top = sorted(
        rows,
        key=lambda item: (-risk_rank(item.get("risk_level", "")), item.get("published_at", ""), item.get("game_name", "")),
    )
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in top:
        buckets[content_group(item)].append(item)
    medium_high = sum(1 for item in rows if risk_rank(item.get("risk_level", "")) >= 2)
    url_count = sum(1 for item in rows if item.get("url"))
    observation_note = f"本轮纳入 {len(rows)} 条厂商相关事件，其中 {url_count} 条带 URL；中高风险 {medium_high} 条。"
    sections = []
    for key, label, icon in CONTENT_GROUPS:
        items = buckets.get(key, [])
        cards = "".join(company_event_card(item) for item in items[:4])
        if not cards:
            cards = "<div class='empty mini-empty'>本轮暂无此类重点。</div>"
        sections.append(
            f"""
            <section class="company-category">
              <div class="category-head">
                <h4><i data-lucide="{esc(icon)}"></i>{esc(label)}</h4>
                <span>{len(items)} 条</span>
              </div>
              <div class="company-events">{cards}</div>
            </section>
            """
        )
    grouped_lines = "".join(sections) if rows else "<div class='empty'>等待本轮社区事件回填。</div>"
    return f"""
      <article class="glass-card company-card {accent_class}">
        <div class="card-title">
          <div><span class="eyebrow">{esc(company)}舆情观察</span><h3>{esc(company)}</h3></div>
          <span class="score">{len(rows)}</span>
        </div>
        <p class="company-note">{esc(observation_note)}</p>
        <div class="tag-cloud">{tag_cloud(rows)}</div>
        <div class="focus-games">{hit_games}</div>
        <div class="company-categories">{grouped_lines}</div>
      </article>
    """


def high_risk_cards(records: list[dict[str, Any]]) -> str:
    items = [item for item in records if item.get("risk_level") == "high" and not is_raw_json_fragment_record(item)]
    cards = []
    for item in items[:2]:
        cards.append(
            f"""
            <article class="risk-card risk-card-high">
              <div class="risk-head"><span>{esc(risk_text(item.get('risk_level')))}</span><b>{esc(display_text(item.get('game_name')))}</b></div>
              <h3>{esc(display_compact(item.get('title'), 120, '未命名事件'))}</h3>
              <p>{esc(display_compact(item.get('summary') or item.get('why_watch'), 220))}</p>
              <footer><span>{esc(display_platform(item.get('platform')))}</span>{f'<a href="{esc(item.get("url"))}" target="_blank" rel="noreferrer">查看链接</a>' if item.get('url') else '<span>辅助样本</span>'}</footer>
            </article>
            """
        )
    return "".join(cards) or "<div class='empty'>暂无高风险预警。</div>"


def evidence_rows(records: list[dict[str, Any]]) -> str:
    rows = []
    for item in sorted(records, key=lambda row: (-risk_rank(row.get("risk_level", "")), row.get("company", ""), row.get("game_name", ""))):
        if is_raw_json_fragment_record(item):
            continue
        company = item.get("company") or "其他"
        filter_company = company if company in {"米哈游", "库洛"} else "其他"
        sample_link = evidence_link(item, "\u67e5\u770b\u94fe\u63a5")
        level = evidence_badge(item.get("evidence_level"), bool(item.get("url")))
        title = display_compact(item.get("title") or item.get("summary"), 100, "待复核事件")
        plain = compact_content(item.get("plain_summary") or item.get("summary") or item.get("title"), 180) or title
        why = compact_content(item.get("why_watch"), 150)
        business_use = compact_content(item.get("business_use"), 130)
        details = "".join(
            f"<p><span>{esc(label)}</span>{esc(text)}</p>"
            for label, text in [
                ("说明：", plain),
                ("关注：", why),
                ("业务：", business_use),
            ]
            if text
        )
        rows.append(
            "<tr "
            f"data-company='{esc(filter_company)}'>"
            f"<td><span class='game-name'>{esc(display_text(item.get('game_name')))}</span><small>{esc(display_text(company))}</small></td>"
            f"<td class='event-cell'><b>{esc(title)}</b><div class='event-cell-details'>{details}</div></td>"
            f"<td><div class='label-stack'>{level}<span class='risk-pill {risk_class(item.get('risk_level'))}'>{esc(risk_text(item.get('risk_level')))}</span></div></td>"
            f"<td>{esc(display_platform(item.get('platform')))}</td>"
            f"<td class='action-cell'>{sample_link}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='5' class='empty'>\u6682\u65e0\u5e26 URL \u7ebf\u7d22\u3002\u5b8c\u6210\u7f51\u9875\u8f6e\u8be2\u540e\u91cd\u65b0\u6e32\u67d3\u5373\u53ef\u586b\u5145\u3002</td></tr>"


def evidence_level_label(value: Any) -> str:
    text = str(value or "").strip()
    return {
        "core": "URL待复核",
        "core_evidence": "URL待复核",
        "supporting": "辅助观察",
        "secondary_only": "待验证线索",
        "auxiliary_sample": "辅助样本",
        "pending_lead": "待验证",
        "pending": "待验证",
        "excluded": "排除",
    }.get(text, text or "URL待复核")


def evidence_level_kind(value: Any, has_url: bool = False) -> str:
    text = str(value or "").strip().lower()
    if text in {"core", "core_evidence"} or has_url:
        return "core"
    if text in {"auxiliary_sample", "supporting", "secondary", "secondary_only"}:
        return "aux"
    if text in {"pending", "pending_lead", "needs_verification", "excluded"}:
        return "pending"
    return "pending" if not has_url else "core"


def evidence_badge(value: Any, has_url: bool = False) -> str:
    kind = evidence_level_kind(value, has_url)
    label = evidence_level_label(value)
    if kind == "core":
        label = "URL待复核"
    elif kind == "aux":
        label = "辅助样本"
    elif kind == "pending":
        label = "待验证"
    return f"<span class='evidence-badge evidence-{kind}'>{esc(label)}</span>"


def infer_tendency(item: dict[str, Any]) -> str:
    text = " ".join(
        display_text(item.get(key))
        for key in ["player_tendency", "player_intent", "summary", "specific_player_opinions", "why_watch", "title"]
    )
    rules = [
        ("退坑", ["退坑", "流失", "弃坑", "劝退"]),
        ("回流", ["回流", "回坑", "回归"]),
        ("抽卡", ["抽卡", "卡池", "自选", "专武", "角色"]),
        ("付费", ["付费", "氪金", "礼包", "价格", "福利少"]),
        ("观望", ["观望", "犹豫", "再看", "等版本", "未决定"]),
        ("推荐", ["推荐", "入坑", "安利"]),
        ("建议", ["建议", "希望", "优化", "减负", "改善"]),
    ]
    for label, markers in rules:
        if any(marker in text for marker in markers):
            return label
    return "未明确"


def tendency_structure(records: list[dict[str, Any]]) -> tuple[str, str]:
    clean = [item for item in records if not is_raw_json_fragment_record(item)]
    if not clean:
        return "样本不足，暂不判断玩家倾向变化。", "<article class='tendency-card'><div class='tendency-top'><span>主导倾向</span><b>暂无样本</b></div><dl><dt>关联游戏</dt><dd>等待社区样本回填</dd><dt>触发点</dt><dd>暂无具体触发点</dd><dt>本轮判断说明</dt><dd>仅展示本轮结构，不做同比/环比判断。</dd></dl></article>"

    tendencies = Counter(infer_tendency(item) for item in clean)
    total = sum(tendencies.values())
    top_name, top_count = tendencies.most_common(1)[0]
    if total < 3:
        headline = f"本轮有效样本 {total} 条，样本偏少，只展示本轮结构，不判断升降。"
    elif top_count / max(total, 1) >= 0.5:
        headline = f"本轮以“{top_name}”为主导倾向，占 {top_count}/{total}；由于未接入历史基线，只说明本轮结构，不做同比/环比。"
    else:
        headline = f"本轮玩家倾向较分化，前两类为 {'、'.join(name for name, _ in tendencies.most_common(2))}；这里只说明本轮结构，不做同比/环比。"

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in clean:
        grouped[infer_tendency(item)].append(item)

    cards = []
    for name, count in tendencies.most_common(6):
        items = grouped.get(name, [])
        games = []
        triggers = []
        for item in items:
            game = display_text(item.get("game_name"))
            if game and game not in games:
                games.append(game)
            trigger = compact_content(item.get("plain_summary") or item.get("title") or item.get("summary"), 76)
            if trigger and trigger not in triggers:
                triggers.append(trigger)
        games_text = "、".join(games[:4]) or "未归类游戏"
        trigger_text = "；".join(triggers[:3]) or "等待具体触发点"
        if count == top_count and name == top_name:
            note = f"该倾向在本轮样本中占 {count}/{total}，是当前最明显的方向；仅代表本轮结构，不做同比/环比。"
        else:
            note = f"该倾向在本轮样本中占 {count}/{total}，作为辅助观察；仅代表本轮结构，不做同比/环比。"
        cards.append(
            f"""
            <article class="tendency-card">
              <div class="tendency-top"><span>主导倾向</span><b>{esc(name)}</b><small>{count}/{total}</small></div>
              <dl>
                <dt>关联游戏</dt><dd>{esc(games_text)}</dd>
                <dt>触发点</dt><dd>{esc(trigger_text)}</dd>
                <dt>本轮判断说明</dt><dd>{esc(note)}</dd>
              </dl>
            </article>
            """
        )
    return headline, "".join(cards)


def suggestion_groups(records: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for item in records:
        if is_raw_json_fragment_record(item):
            continue
        game = display_text(item.get("game_name")) or "未归类游戏"
        text = compact_content(item.get("specific_player_opinions"), 170)
        if not text:
            continue
        key = (game, re.sub(r"\W+", "", text).casefold()[:90])
        if key in seen:
            continue
        seen.add(key)
        grouped[game].append(text)

    if not grouped:
        return "<div class='empty'>等待具体玩家建议回填。</div>"

    cards = []
    for game, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:8]:
        lines = "".join(f"<li>{esc(text)}</li>" for text in items[:3])
        extra = len(items) - 3
        more = f"<small>另有 {extra} 条同游戏建议已折叠</small>" if extra > 0 else ""
        cards.append(
            f"""
            <article class="suggestion-card">
              <div class="suggestion-head"><b>{esc(game)}</b><span>{min(len(items), 3)} 条关键建议</span></div>
              <ul>{lines}</ul>
              {more}
            </article>
            """
        )
    return "".join(cards)


def insight_cards(records: list[dict[str, Any]]) -> str:
    headline, trend_lines = tendency_structure(records)
    suggestion_lines = suggestion_groups(records)
    return f"""
      <div class="insight-panel">
        <h3><i data-lucide="activity"></i>玩家倾向变化</h3>
        <p>{esc(headline)}</p>
        <div class="tendency-grid">{trend_lines}</div>
      </div>
      <div class="insight-panel">
        <h3><i data-lucide="lightbulb"></i>玩家建议</h3>
        <div class="suggestion-groups">{suggestion_lines}</div>
      </div>
    """


EMPTY_PENDING_TEXTS = {
    "",
    "线索",
    "待人工复核线索",
    "待验证线索缺少具体摘要，需回看原始输出。",
    "信息不足，需人工复核后判断。",
    "仅作待核验线索，不建议外部使用。",
    "无URL但值得核验的线索",
    "无 URL 但值得核验的线索",
    "无url但值得核验的线索",
    "暂无",
    "未提供",
    "none",
    "null",
}


def compact_content(value: Any, max_chars: int = 160, fallback: str = "") -> str:
    text = display_compact(value, max_chars, fallback)
    folded = text.strip().casefold()
    if not text or folded in EMPTY_PENDING_TEXTS or is_status_only_text(text):
        return ""
    return text


def pending_lead_body(item: dict[str, Any]) -> str:
    raw_probe = {
        "title": item.get("title") or item.get("lead"),
        "summary": item.get("summary"),
        "specific_player_opinions": item.get("specific_player_opinions"),
        "why_watch": item.get("why_watch"),
    }
    if is_raw_json_fragment_record(raw_probe):
        return ""
    for key in ["lead", "summary", "title", "specific_player_opinions", "why_watch"]:
        value = item.get(key)
        if is_status_only_text(value):
            continue
        text = display_compact(value, 180)
        folded = text.strip().casefold()
        if not text or folded in EMPTY_PENDING_TEXTS:
            continue
        if len(re.sub(r"\W+", "", text)) < 6:
            continue
        return text
    return ""


def pending_cards(pending: list[dict[str, Any]]) -> str:
    visible_pending = visible_pending_leads(pending)
    if not visible_pending:
        return "<div class='empty'>暂无待验证线索。</div>"
    cards = []
    for item in visible_pending[:18]:
        reason = str(item.get("reason") or "needs_verification")
        confidence = 35 if reason == "no_url" else 55
        level = evidence_badge(item.get("evidence_level") or "pending_lead", False)
        risk = f"<span class='risk-pill {risk_class(item.get('risk_level'))}'>{esc(risk_text(item.get('risk_level')))}</span>"
        verification = platform_verification_link(item)
        verify_html = ""
        if verification:
            verify_label, verify_url, verify_class = verification
            verify_html = f"<a class='evidence-link verify-link {esc(verify_class)}' href='{esc(verify_url)}' target='_blank' rel='noreferrer'>{esc(verify_label)}</a>"
        why = compact_content(item.get("why_watch"), 120)
        business_use = compact_content(item.get("business_use"), 110)
        cards.append(
            f"""
            <article class="rumor-card">
              <div class="rumor-head"><span>{esc(display_text(item.get('company')) or '未归类')}</span><b>{esc(display_text(item.get('game_name')) or '线索')}</b></div>
              <div class="rumor-tags">{level}{risk}</div>
              <p>{esc(item.get('_display_lead'))}</p>
              {f"<p class='rumor-note'><span>关注：</span>{esc(why)}</p>" if why else ""}
              {f"<p class='rumor-note'><span>业务：</span>{esc(business_use)}</p>" if business_use else ""}
              <div class="progress"><span style="width:{confidence}%"></span></div>
              <footer class="rumor-actions"><small>核验优先级 {confidence}%</small>{verify_html}</footer>
            </article>
            """
        )
    return "".join(cards)


def status_class(item: dict[str, Any]) -> str:
    if item.get("prompt_drift"):
        return "status-warn"
    status = str(item.get("status") or "").lower()
    error = str(item.get("error") or "").lower()
    if status in {"ok", "submitted", "success"} and not error:
        parsed = item.get("parsed_json")
        if parsed is False or item.get("parsed_json_payloads") == 0 and item.get("heuristic_url_items", 0):
            return "status-warn"
        return "status-ok"
    if "user_message_not_confirmed" in error or status in {"error", "parse_error"}:
        return "status-bad"
    return "status-warn"


def status_label(item: dict[str, Any]) -> str:
    if item.get("prompt_drift"):
        return "漂移"
    status = str(item.get("status") or "unknown")
    error = str(item.get("error") or "")
    if status == "ok" and item.get("parsed_json") is False:
        return "已采集 / 待二次结构化"
    if status == "ok":
        return "已采集"
    if error:
        return f"{status}: {error}"
    return status


def platform_status_cards(statuses: list[dict[str, Any]]) -> str:
    if not statuses:
        return "<div class='empty'>暂无平台状态记录。</div>"
    cards = []
    for item in statuses[:18]:
        counts = []
        for key, label in [
            ("evidence_count", "证据"),
            ("pending_count", "线索"),
            ("parsed_json_payloads", "JSON块"),
            ("heuristic_url_items", "URL抽取"),
        ]:
            if item.get(key) not in {None, ""}:
                counts.append(f"{label} {item.get(key)}")
        fallback = "建议短 prompt fallback" if item.get("fallback_recommended") else "无需 fallback"
        cards.append(
            f"""
            <article class="status-card {status_class(item)}">
              <div><b>{esc(item.get('ai_tool') or '未知平台')}</b><span>{esc(item.get('prompt_id') or '')}</span></div>
              <p>{esc(status_label(item))}</p>
              <small>{esc(' / '.join(counts) or fallback)} · {esc(fallback)}</small>
            </article>
            """
        )
    return "".join(cards)


def hit_game_chips(records: list[dict[str, Any]]) -> str:
    grouped: dict[tuple[str, str], int] = defaultdict(int)
    for item in records:
        game = display_text(item.get("game_name"))
        company = canonical_company_name(item.get("company") or "其他")
        if not game or game in {"二游大盘", "大盘"} or is_placeholder_record(item):
            continue
        grouped[(company, game)] += 1
    if not grouped:
        return "<div class='empty'>本轮尚未命中具体游戏。</div>"
    chips = []
    for (company, game), count in sorted(grouped.items(), key=lambda pair: (-pair[1], pair[0][0], pair[0][1]))[:24]:
        chips.append(f"<span class='hit-game'>{esc(game)}<small>{esc(company)} / {count} 条</small></span>")
    return f"<div class='hit-games'>{''.join(chips)}</div>"


def visible_pending_leads(pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for item in pending:
        body = pending_lead_body(item)
        if not body:
            continue
        body_key = re.sub(r"\W+", "", display_text(body)).casefold()[:90]
        game_key = re.sub(r"\W+", "", display_text(item.get("game_name"))).casefold()
        key = f"{game_key}|{body_key}" if game_key else body_key
        if key in seen:
            continue
        seen.add(key)
        row = dict(item)
        row["_display_lead"] = body
        rows.append(row)
    return rows


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def count_core_evidence(records: list[dict[str, Any]]) -> int:
    return sum(1 for item in records if item.get("url") and not is_raw_json_fragment_record(item))


def count_auxiliary_samples(pending: list[dict[str, Any]]) -> int:
    return sum(1 for item in visible_pending_leads(pending) if not item.get("url"))


def raw_audit_summary_section(metadata: dict[str, Any]) -> str:
    return ""


def count_medium_high(records: list[dict[str, Any]], pending: list[dict[str, Any]]) -> int:
    rows = [item for item in records if not is_raw_json_fragment_record(item)] + visible_pending_leads(pending)
    return sum(1 for item in rows if risk_rank(item.get("risk_level", "")) >= 2)


def metadata_hit_games(metadata: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_hits = metadata.get("hit_games")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_hits, list):
        for item in raw_hits:
            if isinstance(item, dict):
                name = display_text(item.get("game_name") or item.get("name") or item.get("game"))
                if not name:
                    continue
                rows.append(
                    {
                        "game_name": name,
                        "company": canonical_company_name(item.get("company") or item.get("category") or "其他"),
                        "count": to_int(item.get("count") or item.get("hit_count") or item.get("evidence_count"), 1),
                        "core": to_int(item.get("core_evidence_count"), 0),
                        "auxiliary": to_int(item.get("auxiliary_count"), 0),
                    }
                )
            else:
                name = display_text(item)
                if name:
                    rows.append({"game_name": name, "company": "关注矩阵", "count": 1})
    if rows:
        return rows

    grouped: dict[tuple[str, str], int] = defaultdict(int)
    for item in records:
        game = display_text(item.get("game_name"))
        company = canonical_company_name(item.get("company") or item.get("category") or "其他")
        if not game or game in {"二游大盘", "大盘"} or is_placeholder_record(item):
            continue
        grouped[(company, game)] += 1
    return [
        {"company": company, "game_name": game, "count": count}
        for (company, game), count in sorted(grouped.items(), key=lambda pair: (-pair[1], pair[0][0], pair[0][1]))
    ]


def hit_games_section(metadata: dict[str, Any], records: list[dict[str, Any]]) -> str:
    hit_rows = metadata_hit_games(metadata, records)
    watch_count = to_int(metadata.get("watch_game_count"), 0)
    hit_count = to_int(metadata.get("hit_game_count"), len(hit_rows))
    unhit_count = to_int(metadata.get("unhit_game_count"), max(watch_count - hit_count, 0))
    chips = ""
    for item in hit_rows[:36]:
        core = to_int(item.get("core"), 0)
        auxiliary = to_int(item.get("auxiliary"), 0)
        detail = f"核心 {core} / 辅助 {auxiliary}" if core or auxiliary else f"{item.get('count') or 1} 条"
        chips += f"<span class='hit-game'><b>{esc(item['game_name'])}</b><small>{esc(item.get('company') or '关注矩阵')} / {esc(detail)}</small></span>"
    if not chips:
        chips = "<div class='empty'>本轮关注矩阵尚未命中具体游戏。请在下一轮 Web AI 采集中继续只返回本周期有实际公开信息的项目。</div>"
    return f"""
      <div class="matrix-summary">
        <span>关注游戏数 <b>{watch_count or hit_count}</b></span>
        <span>本轮命中 <b>{hit_count}</b></span>
        <span>未命中 <b>{unhit_count}</b></span>
      </div>
      <div class="hit-games">{chips}</div>
    """


def category_lens_section() -> str:
    lenses = [
        ("seedling", "米哈游新增赛道观察", "休闲种田/类动森、宠物养成", "观察米哈游在慢节奏生活模拟、陪伴式养成和长线内容消费上的外部参照。"),
        ("crosshair", "库洛潜在方向观察", "搜打撤/撤离射击类、动作竞技、硬核战斗向", "观察库洛在高操作门槛、强战斗反馈和竞技化内容上的潜在机会与风险。"),
        ("globe-2", "双方共同关注方向", "3A 化、开放世界、高品质内容生产、跨端体验", "观察高规格内容、全球化传播和跨端体验对二游产品预期的影响。"),
    ]
    return "".join(
        f"""
        <article class="lens-card">
          <div><i data-lucide="{icon}"></i><span>{esc(title)}</span></div>
          <h3>{esc(scope)}</h3>
          <p>{esc(note)}</p>
        </article>
        """
        for icon, title, scope, note in lenses
    )


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "是"}


SECTOR_KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("新品测试 / 预约 / PV", ("新品", "测试", "首测", "二测", "封测", "预约", "招募", "PV", "预告", "Demo", "试玩")),
    ("宠物养成", ("宠物", "捉宠", "养成", "精灵", "宠物养成")),
    ("搜打撤", ("搜打撤", "撤离", " extraction", "Extraction", "撤离射击")),
    ("动作竞技", ("动作竞技", "竞技", "格斗", "PVP", "PvP", "战斗", "硬核动作")),
    ("开放世界 / 3A 化", ("开放世界", "3A", "高品质内容", "跨端", "大世界")),
    ("休闲种田", ("休闲种田", "种田", "农场", "生活模拟", "经营", "田园")),
    ("生活方式内容", ("生活方式", "种草", "穿搭", "家园", "装扮", "社交内容")),
]


FEMALE_ONLY_MARKERS = ("女性向", "乙女", "女频", "女性玩家")


def sector_label_for_item(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in [
            "sector",
            "category",
            "game_name",
            "title",
            "summary",
            "plain_summary",
            "lead",
            "why_watch",
            "business_use",
            "platform",
        ]
    )
    for label, markers in SECTOR_KEYWORD_RULES:
        if any(marker in text for marker in markers):
            return label
    if any(marker in text for marker in FEMALE_ONLY_MARKERS):
        return ""
    return ""


def is_sector_item(item: dict[str, Any]) -> bool:
    return bool(sector_label_for_item(item))


def sector_cases_section(metadata: dict[str, Any], records: list[dict[str, Any]], pending: list[dict[str, Any]]) -> str:
    raw_items = metadata.get("sector_items") if isinstance(metadata.get("sector_items"), list) else []
    candidates = [item for item in raw_items if isinstance(item, dict)] + [
        item for item in records + visible_pending_leads(pending) if is_sector_item(item)
    ]
    seen: set[str] = set()
    cards: list[str] = []
    for item in candidates:
        if is_raw_json_fragment_record(item):
            continue
        title = display_compact(item.get("title") or item.get("plain_summary") or item.get("summary") or item.get("lead"), 110)
        body = compact_content(item.get("plain_summary") or item.get("summary") or item.get("lead"), 180)
        if not title and not body:
            continue
        sector = sector_label_for_item(item)
        if not sector:
            continue
        key = re.sub(r"\W+", "", f"{sector}|{title}|{body}").casefold()[:140]
        if key in seen:
            continue
        seen.add(key)
        why = compact_content(item.get("why_watch"), 120)
        business = compact_content(item.get("business_use"), 110)
        action = evidence_link(item) if item.get("url") else ""
        cards.append(
            f"""
            <article class="sector-card">
              <div class="sector-head"><span>{esc(sector)}</span>{evidence_badge(item.get('evidence_level'), bool(item.get('url')))}</div>
              <h3>{esc(title or body)}</h3>
              {f"<p>{esc(body)}</p>" if body and body != title else ""}
              {f"<p><b>为什么看：</b>{esc(why)}</p>" if why else ""}
              {f"<p><b>业务使用：</b>{esc(business)}</p>" if business else ""}
              <footer><small>{esc(display_text(item.get('game_name')) or display_text(item.get('company')) or '行业案例')}</small>{action}</footer>
            </article>
            """
        )
        if len(cards) >= 12:
            break
    if not cards:
        return "<div class='empty'>本轮尚未采集到可展示的赛道新闻或案例；下一轮周报 prompt 会继续要求 Web AI 返回具体案例，而不是只解释赛道定义。</div>"
    return f"<div class='sector-grid'>{''.join(cards)}</div>"


def non_key_company_section(metadata: dict[str, Any], records: list[dict[str, Any]], pending: list[dict[str, Any]]) -> str:
    raw_items = metadata.get("non_key_company_items") if isinstance(metadata.get("non_key_company_items"), list) else []
    candidates = [item for item in raw_items if isinstance(item, dict)]
    if not candidates:
        candidates = [
            item
            for item in records + visible_pending_leads(pending)
            if canonical_company_name(item.get("company")) not in {"米哈游", "库洛"} and display_text(item.get("game_name")) not in {"二游大盘", "大盘", ""}
        ]
    seen: set[str] = set()
    cards: list[str] = []
    for item in candidates:
        title = display_compact(item.get("title") or item.get("plain_summary") or item.get("summary") or item.get("lead"), 110)
        body = compact_content(item.get("plain_summary") or item.get("summary") or item.get("lead"), 170)
        game = display_text(item.get("game_name")) or display_text(item.get("company")) or "其他二游"
        if not title and not body:
            continue
        key = re.sub(r"\W+", "", f"{game}|{title}|{body}").casefold()[:130]
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            f"""
            <article class="compact-event">
              <div><b>{esc(game)}</b><span>{esc(display_platform(item.get('platform')))}</span></div>
              <h3>{esc(title or body)}</h3>
              {f"<p>{esc(body)}</p>" if body and body != title else ""}
              <footer>{evidence_badge(item.get('evidence_level'), bool(item.get('url')))}{evidence_link(item)}</footer>
            </article>
            """
        )
        if len(cards) >= 10:
            break
    if not cards:
        return "<div class='empty'>本轮尚未形成足够清晰的其他二游/竞品动态；建议下一轮优先使用周报扩容 prompt。</div>"
    return f"<div class='compact-event-grid'>{''.join(cards)}</div>"


def key_conclusions(records: list[dict[str, Any]], pending: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    clean = [item for item in records if not is_raw_json_fragment_record(item)]
    lines = []
    top_items = sorted(clean, key=lambda item: (-risk_rank(item.get("risk_level", "")), item.get("company", ""), item.get("game_name", "")))[:2]
    for item in top_items:
        title = display_compact(item.get("plain_summary") or item.get("summary") or item.get("title"), 110, "待复核事件")
        why = display_compact(item.get("why_watch") or item.get("business_use"), 120)
        if why:
            lines.append(f"{display_text(item.get('game_name')) or display_text(item.get('company'))}：{title}。关注原因：{why}")
        else:
            lines.append(f"{display_text(item.get('game_name')) or display_text(item.get('company'))}：{title}。")
    return "".join(f"<li>{esc(line)}</li>" for line in lines)


def source_scope_section(
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    platform_status: list[dict[str, Any]],
    lookback_days: int,
    start_label: str,
    report_date: str,
) -> str:
    tools = []
    for item in records + pending + platform_status:
        name = str(item.get("source_ai") or item.get("ai_tool") or "").strip()
        if name and name not in tools:
            tools.append(name)
    tool_text = "、".join(tools[:10]) or "元宝、豆包、知乎直答、点点、Gemini/Grok 等 Web AI 工具"
    return f"""
      <div class="scope-grid">
        <article class="scope-card"><span>时间窗口</span><p>最近 {lookback_days} 天，{esc(start_label)} 至 {esc(report_date)}。</p></article>
        <article class="scope-card"><span>使用 AI 工具</span><p>{esc(tool_text)}</p></article>
        <article class="scope-card"><span>覆盖类型</span><p>官方公告、新闻、X/B站/微博/知乎/小红书等公开可检索样本，以及 Web AI 对公开讨论的汇总观察。</p></article>
      </div>
    """


def render_html(
    records: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    errors: list[str],
    platform_status: list[dict[str, Any]],
    metadata: dict[str, Any],
    title: str,
    report_date: str,
    lookback_days: int,
    show_platform_status: bool = False,
) -> str:
    mihoyo = company_records(records, "米哈游")
    kuro = company_records(records, "库洛")
    chart = json.dumps(chart_payload(records, report_date, lookback_days), ensure_ascii=False)
    start_label = date_labels(report_date, lookback_days)[0]
    report_mode = str(metadata.get("report_mode") or ("weekly" if lookback_days >= 7 else "daily"))
    period_label = "本周" if report_mode == "weekly" or lookback_days >= 7 else "今日"
    report_kind = "周报" if report_mode == "weekly" or lookback_days >= 7 else "日报"
    core_count = count_core_evidence(records)
    auxiliary_count = count_auxiliary_samples(pending)
    hit_game_count = to_int(metadata.get("hit_game_count"), len(metadata_hit_games(metadata, records)))
    watch_game_count = to_int(metadata.get("watch_game_count"), hit_game_count)
    unhit_game_count = to_int(metadata.get("unhit_game_count"), max(watch_game_count - hit_game_count, 0))
    medium_high_count = count_medium_high(records, pending)
    hit_games = hit_games_section(metadata, records)
    key_items = key_conclusions(records, pending, metadata)
    sector_cases = sector_cases_section(metadata, records, pending)
    non_key_cases = non_key_company_section(metadata, records, pending)
    source_scope = source_scope_section(metadata, records, pending, platform_status, lookback_days, start_label, report_date)
    parse_note = f"<p class='parse-note'>解析提示：{esc(display_compact('；'.join(errors[:3]), 260))}</p>" if errors and show_platform_status else ""
    platform_status_section = ""
    if show_platform_status:
        platform_status_section = f"""
      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="route"></i>平台采集状态</h2><span class="module-sub">调试视图：区分已采集、待二次结构化、prompt drift、发送未确认和 fallback 建议</span></div>
        <div class="status-grid">{platform_status_cards(platform_status)}</div>
      </section>
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    :root {{
      --bg:#0B0F19;
      --panel:rgba(15,23,42,.72);
      --line:rgba(148,163,184,.18);
      --text:#E5E7EB;
      --muted:#94A3B8;
      --blue:#3B82F6;
      --purple:#8B5CF6;
      --green:#10B981;
      --amber:#F59E0B;
      --red:#EF4444;
      --mihoyo:#00F2FE;
      --kuro:#FF3366;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      min-height:100vh;
      background:
        radial-gradient(circle at 12% 8%, rgba(59,130,246,.24), transparent 34%),
        radial-gradient(circle at 84% 4%, rgba(139,92,246,.22), transparent 30%),
        linear-gradient(135deg, #0B0F19 0%, #0F172A 52%, #111827 100%);
      color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;
      letter-spacing:0;
    }}
    .dashboard {{ width:min(1480px, calc(100% - 32px)); margin:0 auto; padding:28px 0 44px; }}
    .dashboard main.grid {{ grid-template-columns:minmax(0,1fr); }}
    .dashboard main > * {{ min-width:0; }}
    .glass-card {{
      background:linear-gradient(180deg, rgba(15,23,42,.82), rgba(15,23,42,.58));
      border:1px solid var(--line);
      border-radius:22px;
      box-shadow:0 20px 60px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.05);
      backdrop-filter:blur(18px);
      min-width:0;
    }}
    .hero {{ padding:26px; position:relative; overflow:hidden; }}
    .hero:after {{ content:""; position:absolute; right:0; bottom:-80px; width:min(760px,70%); height:220px; background:linear-gradient(90deg, rgba(0,242,254,.16), rgba(139,92,246,.2)); filter:blur(34px); pointer-events:none; }}
    .hero h1 {{ font-size:clamp(24px,3vw,42px); line-height:1.12; margin:0; font-weight:800; }}
    .hero p {{ color:var(--muted); margin:10px 0 0; }}
    .hero > .flex {{ display:flex; flex-direction:column; gap:20px; position:relative; z-index:10; min-width:0; }}
    .hero > .flex > div {{ min-width:0; max-width:100%; }}
    .hero .flex-wrap {{ display:flex; flex-wrap:wrap; gap:10px; min-width:0; }}
    .hero .tag {{ max-width:100%; overflow-wrap:anywhere; }}
    .status-dot {{ display:inline-flex; align-items:center; gap:8px; color:#BBF7D0; }}
    .status-dot:before {{ content:""; width:9px; height:9px; border-radius:50%; background:var(--green); box-shadow:0 0 16px var(--green); }}
    .kpi-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; margin-top:18px; }}
    .kpi {{ padding:18px; }}
    .kpi .label {{ color:var(--muted); font-size:13px; display:flex; gap:8px; align-items:center; }}
    .kpi .value {{ font-size:32px; font-weight:800; margin-top:10px; }}
    .kpi .delta {{ margin-top:8px; font-size:13px; color:#BFDBFE; }}
    .kpi.warning {{ border-color:rgba(239,68,68,.5); box-shadow:0 0 0 1px rgba(239,68,68,.2), 0 20px 60px rgba(239,68,68,.12); }}
    .metric-note {{ margin:14px 0 0; color:#CBD5E1; font-size:13px; line-height:1.7; }}
    .audit-summary {{ position:relative; z-index:10; display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; margin-top:14px; }}
    .audit-summary article {{ border:1px solid rgba(148,163,184,.16); border-radius:16px; padding:12px; background:rgba(2,6,23,.28); min-width:0; }}
    .audit-summary span {{ display:block; color:#A5B4FC; font-size:12px; font-weight:800; overflow-wrap:anywhere; }}
    .audit-summary b {{ display:block; margin-top:5px; color:#F8FAFC; font-size:22px; }}
    .audit-summary small {{ display:block; margin-top:4px; color:#94A3B8; font-size:11px; line-height:1.4; overflow-wrap:anywhere; }}
    .module {{ padding:20px; min-width:0; }}
    .module-head {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:16px; min-width:0; flex-wrap:wrap; }}
    .module h2 {{ margin:0; font-size:20px; font-weight:800; display:flex; align-items:center; gap:9px; }}
    .module-sub {{ color:var(--muted); font-size:13px; overflow-wrap:anywhere; }}
    .conclusion-list {{ list-style:none; margin:0; padding:0; display:grid; gap:10px; }}
    .conclusion-list li {{ border:1px solid rgba(148,163,184,.14); border-radius:16px; padding:13px 14px; background:rgba(2,6,23,.26); color:#E2E8F0; line-height:1.7; }}
    .lens-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .lens-card {{ border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:16px; background:rgba(15,23,42,.42); }}
    .lens-card div {{ display:flex; align-items:center; gap:8px; color:#A5B4FC; font-size:13px; font-weight:800; }}
    .lens-card h3 {{ margin:12px 0 8px; font-size:18px; line-height:1.35; }}
    .lens-card p {{ margin:0; color:#CBD5E1; line-height:1.7; font-size:13px; }}
    .sector-grid, .compact-event-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; }}
    .sector-card, .compact-event {{ border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:16px; background:rgba(15,23,42,.48); min-width:0; }}
    .sector-head, .compact-event div, .sector-card footer, .compact-event footer {{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }}
    .sector-head span {{ color:#A5B4FC; font-size:12px; font-weight:900; border:1px solid rgba(165,180,252,.22); border-radius:999px; padding:4px 9px; }}
    .sector-card h3, .compact-event h3 {{ margin:12px 0 8px; color:#F8FAFC; font-size:17px; line-height:1.45; font-weight:850; overflow-wrap:anywhere; }}
    .sector-card p, .compact-event p {{ margin:8px 0 0; color:#CBD5E1; line-height:1.7; font-size:13px; overflow-wrap:anywhere; }}
    .sector-card p b {{ color:#93C5FD; }}
    .sector-card small, .compact-event span {{ color:var(--muted); font-size:12px; }}
    .compact-event b {{ color:#F8FAFC; overflow-wrap:anywhere; }}
    .matrix-summary {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; }}
    .matrix-summary span {{ border:1px solid rgba(148,163,184,.16); border-radius:14px; padding:10px 12px; background:rgba(15,23,42,.46); color:#CBD5E1; }}
    .matrix-summary b {{ color:#F8FAFC; font-size:18px; margin-left:5px; }}
    .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
    .company-block {{ display:grid; gap:14px; }}
    .chart-box {{ height:330px; }}
    .company-card {{ padding:20px; position:relative; overflow:hidden; }}
    .company-card:before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; background:var(--mihoyo); }}
    .company-card.kuro:before {{ background:var(--kuro); }}
    .card-title {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; }}
    .eyebrow {{ font-size:12px; color:var(--muted); text-transform:uppercase; }}
    .company-card h3 {{ font-size:26px; margin:3px 0 0; font-weight:800; }}
    .score {{ display:grid; place-items:center; min-width:58px; height:58px; border-radius:18px; background:rgba(59,130,246,.14); color:#DBEAFE; font-size:22px; font-weight:800; }}
    .company-note {{ margin:12px 0 0; color:#CBD5E1; line-height:1.7; font-size:13px; }}
    .tag-cloud {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }}
    .tag {{ border:1px solid rgba(148,163,184,.18); background:rgba(148,163,184,.08); color:#CBD5E1; padding:5px 10px; border-radius:999px; font-size:12px; }}
    .focus-games {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
    .focus-game {{ display:inline-flex; align-items:center; gap:7px; border:1px solid rgba(148,163,184,.18); background:rgba(15,23,42,.58); color:#CBD5E1; padding:7px 10px; border-radius:999px; font-size:12px; }}
    .focus-game b {{ color:#F8FAFC; }}
    .company-events {{ display:grid; gap:12px; }}
    .company-categories {{ display:grid; gap:16px; }}
    .company-category {{ border:1px solid rgba(148,163,184,.14); border-radius:18px; padding:12px; background:rgba(15,23,42,.28); }}
    .category-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; }}
    .category-head h4 {{ margin:0; display:flex; align-items:center; gap:8px; color:#BFDBFE; font-size:14px; font-weight:800; }}
    .category-head span {{ color:#94A3B8; font-size:12px; }}
    .company-event {{ border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:14px; background:rgba(2,6,23,.34); }}
    .company-event:hover {{ transform:translateY(-1px); border-color:rgba(147,197,253,.35); transition:.18s ease; }}
    .event-meta {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; color:#A5B4FC; font-size:12px; margin-bottom:9px; }}
    .event-title {{ display:block; color:#F8FAFC; font-size:15px; font-weight:800; line-height:1.45; }}
    .company-event p {{ margin:8px 0 0; color:#CBD5E1; font-size:13px; line-height:1.65; }}
    .event-fields {{ display:grid; gap:9px; margin-top:10px; }}
    .event-field {{ border-left:2px solid rgba(148,163,184,.24); padding-left:10px; }}
    .event-field span {{ display:block; color:#94A3B8; font-size:12px; font-weight:800; margin-bottom:2px; }}
    .event-field p {{ margin:0; color:#CBD5E1; overflow-wrap:anywhere; }}
    .event-opinion p {{ color:#D8B4FE !important; }}
    .event-watch p {{ color:#BFDBFE !important; }}
    .event-business p {{ color:#A7F3D0 !important; }}
    .company-event footer {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-top:12px; color:var(--muted); font-size:12px; }}
    .evidence-badge {{ display:inline-flex; align-items:center; justify-content:center; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:900; line-height:1; white-space:nowrap; }}
    .evidence-core {{ border:1px solid rgba(34,211,238,.46); background:rgba(34,211,238,.14); color:#A5F3FC; box-shadow:inset 0 0 0 1px rgba(255,255,255,.03); }}
    .evidence-aux {{ border:1px solid rgba(168,85,247,.42); background:rgba(168,85,247,.13); color:#E9D5FF; }}
    .evidence-pending {{ border:1px solid rgba(245,158,11,.48); background:rgba(245,158,11,.13); color:#FDE68A; }}
    .evidence-link {{ display:inline-flex; align-items:center; justify-content:center; max-width:100%; min-width:76px; border:1px solid rgba(59,130,246,.38); border-radius:999px; padding:6px 10px; background:rgba(59,130,246,.1); color:#BFDBFE; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .evidence-link.xhs-verify {{ border-color:rgba(236,72,153,.42); background:rgba(236,72,153,.12); color:#FBCFE8; }}
    .evidence-link.tieba-verify {{ border-color:rgba(245,158,11,.46); background:rgba(245,158,11,.12); color:#FDE68A; }}
    .evidence-link.bili-verify {{ border-color:rgba(34,211,238,.42); background:rgba(34,211,238,.1); color:#A5F3FC; }}
    .evidence-link.weibo-verify {{ border-color:rgba(239,68,68,.42); background:rgba(239,68,68,.1); color:#FECACA; }}
    .evidence-link.zhihu-verify {{ border-color:rgba(96,165,250,.46); background:rgba(96,165,250,.12); color:#BFDBFE; }}
    .evidence-link.taptap-verify {{ border-color:rgba(16,185,129,.42); background:rgba(16,185,129,.1); color:#A7F3D0; }}
    .evidence-link.generic-verify {{ border-color:rgba(168,85,247,.42); background:rgba(168,85,247,.1); color:#E9D5FF; }}
    .aux-link {{ display:inline-flex; align-items:center; justify-content:center; min-width:76px; border:1px solid rgba(148,163,184,.18); border-radius:999px; padding:6px 10px; color:#94A3B8; background:rgba(148,163,184,.06); }}
    .mini-notes {{ color:#CBD5E1; font-size:13px; margin-top:14px; }}
    .risk-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px; }}
    .risk-card {{ border:1px solid rgba(148,163,184,.22); border-radius:20px; padding:18px; background:rgba(15,23,42,.58); }}
    .risk-card-high {{ border-color:rgba(239,68,68,.62); background:linear-gradient(180deg, rgba(127,29,29,.28), rgba(15,23,42,.7)); animation:pulseBorder 2.2s infinite; }}
    @keyframes pulseBorder {{ 0%,100% {{ box-shadow:0 0 0 rgba(239,68,68,0); }} 50% {{ box-shadow:0 0 28px rgba(239,68,68,.28); }} }}
    .risk-head {{ display:flex; justify-content:space-between; color:#FCA5A5; font-size:13px; }}
    .risk-card h3 {{ margin:10px 0; font-size:18px; font-weight:800; }}
    .risk-card p {{ color:#FEE2E2; }}
    .risk-card footer {{ display:flex; justify-content:space-between; gap:10px; color:#CBD5E1; font-size:13px; }}
    a {{ color:#93C5FD; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .filter-bar {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }}
    .filter-btn {{ border:1px solid rgba(148,163,184,.18); background:rgba(15,23,42,.9); color:#CBD5E1; border-radius:999px; padding:8px 13px; cursor:pointer; }}
    .filter-btn.active {{ background:linear-gradient(90deg,var(--blue),var(--purple)); color:white; }}
    .table-wrap {{ overflow:auto; border:1px solid rgba(148,163,184,.16); border-radius:18px; }}
    table {{ width:100%; min-width:760px; table-layout:fixed; border-collapse:collapse; }}
    th, td {{ padding:14px; border-bottom:1px solid rgba(148,163,184,.14); text-align:left; vertical-align:top; }}
    th {{ color:#A5B4FC; font-size:12px; text-transform:uppercase; background:rgba(15,23,42,.82); }}
    td {{ color:#E2E8F0; font-size:14px; overflow-wrap:anywhere; word-break:break-word; }}
    th:nth-child(1), td:nth-child(1) {{ width:18%; }}
    th:nth-child(2), td:nth-child(2) {{ width:43%; }}
    th:nth-child(3), td:nth-child(3) {{ width:16%; }}
    th:nth-child(4), td:nth-child(4) {{ width:12%; }}
    th:nth-child(5), td:nth-child(5) {{ width:11%; }}
    tr:last-child td {{ border-bottom:0; }}
    .game-name {{ display:block; font-weight:700; }}
    td small {{ display:block; color:var(--muted); margin-top:3px; }}
    .event-cell b {{ display:block; color:#F8FAFC; line-height:1.45; margin-bottom:7px; }}
    .event-cell-details {{ display:grid; gap:5px; }}
    .event-cell-details p {{ margin:0; color:#CBD5E1; line-height:1.6; font-size:13px; }}
    .event-cell-details span {{ color:#93C5FD; font-weight:800; margin-right:4px; }}
    .label-stack {{ display:flex; flex-direction:column; align-items:flex-start; gap:8px; }}
    .action-cell {{ white-space:normal; }}
    .risk-pill {{ display:inline-flex; border-radius:999px; padding:4px 9px; font-size:12px; font-weight:800; }}
    .risk-high {{ background:rgba(239,68,68,.14); color:#FCA5A5; }}
    .risk-medium {{ background:rgba(245,158,11,.14); color:#FCD34D; }}
    .risk-low {{ background:rgba(16,185,129,.14); color:#86EFAC; }}
    .insight-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
    .insight-panel {{ border:1px solid rgba(148,163,184,.16); border-radius:20px; padding:18px; background:rgba(15,23,42,.45); }}
    .insight-panel h3 {{ display:flex; align-items:center; gap:8px; margin:0 0 12px; font-size:17px; font-weight:800; }}
    .insight-panel p {{ color:#BFDBFE; line-height:1.7; overflow-wrap:anywhere; }}
    .insight-panel ul {{ margin:12px 0 0; padding-left:20px; color:#CBD5E1; }}
    .tendency-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; margin-top:12px; }}
    .tendency-card {{ border:1px solid rgba(148,163,184,.15); border-radius:16px; padding:14px; background:rgba(2,6,23,.28); min-width:0; }}
    .tendency-top {{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:12px; }}
    .tendency-top span {{ color:#94A3B8; font-size:12px; font-weight:800; }}
    .tendency-top b {{ color:#F8FAFC; font-size:18px; overflow-wrap:anywhere; }}
    .tendency-top small {{ color:#A5B4FC; border:1px solid rgba(165,180,252,.26); border-radius:999px; padding:4px 8px; }}
    .tendency-card dl {{ display:grid; gap:8px; margin:0; }}
    .tendency-card dt {{ color:#93C5FD; font-size:12px; font-weight:900; }}
    .tendency-card dd {{ margin:0; color:#CBD5E1; line-height:1.65; font-size:13px; overflow-wrap:anywhere; }}
    .suggestion-groups {{ display:grid; gap:12px; margin-top:12px; }}
    .suggestion-card {{ border:1px solid rgba(148,163,184,.15); border-radius:16px; padding:14px; background:rgba(2,6,23,.28); min-width:0; }}
    .suggestion-head {{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }}
    .suggestion-head b {{ color:#F8FAFC; font-size:15px; overflow-wrap:anywhere; }}
    .suggestion-head span {{ color:#A7F3D0; font-size:12px; border:1px solid rgba(16,185,129,.24); border-radius:999px; padding:4px 8px; }}
    .suggestion-card ul {{ list-style:none; display:grid; gap:8px; margin:12px 0 0; padding:0; }}
    .suggestion-card li {{ color:#CBD5E1; line-height:1.65; font-size:13px; overflow-wrap:anywhere; border-left:2px solid rgba(167,243,208,.32); padding-left:10px; }}
    .suggestion-card small {{ display:block; margin-top:10px; color:#94A3B8; }}
    .structured-list {{ list-style:none; padding-left:0 !important; display:grid; gap:10px; }}
    .structured-list li {{ border:1px solid rgba(148,163,184,.12); border-radius:14px; padding:10px 12px; background:rgba(2,6,23,.24); }}
    .structured-list b {{ display:block; color:#F8FAFC; margin-bottom:4px; }}
    .structured-list span {{ color:#CBD5E1; line-height:1.6; }}
    .rumor-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px; }}
    .rumor-card {{ border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:14px; background:rgba(15,23,42,.46); }}
   .rumor-head {{ display:flex; justify-content:space-between; gap:10px; color:#A5B4FC; font-size:12px; }}
   .rumor-tags {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:9px; }}
   .rumor-card p {{ color:#E2E8F0; font-size:13px; line-height:1.65; overflow-wrap:anywhere; }}
   .rumor-note {{ color:#CBD5E1 !important; }}
   .rumor-note span {{ color:#93C5FD; font-weight:800; margin-right:4px; }}
   .rumor-actions {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-top:10px; }}
   .progress {{ height:7px; border-radius:999px; background:rgba(148,163,184,.16); overflow:hidden; }}
    .progress span {{ display:block; height:100%; border-radius:999px; background:linear-gradient(90deg,var(--blue),var(--purple)); }}
    .rumor-card small, .empty, .parse-note {{ color:var(--muted); }}
    .empty {{ padding:18px; border:1px dashed rgba(148,163,184,.25); border-radius:18px; }}
    .hit-games {{ display:flex; flex-wrap:wrap; gap:10px; }}
    .hit-game {{ display:inline-flex; align-items:center; gap:8px; border:1px solid rgba(148,163,184,.18); border-radius:14px; padding:10px 12px; background:rgba(15,23,42,.48); color:#E2E8F0; }}
    .hit-game small {{ color:var(--muted); }}
    .status-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; }}
    .status-card {{ border:1px solid rgba(148,163,184,.18); border-radius:18px; padding:14px; background:rgba(15,23,42,.48); }}
    .status-card div {{ display:flex; justify-content:space-between; gap:10px; color:#E2E8F0; }}
    .status-card div span {{ color:var(--muted); font-size:12px; }}
    .status-card p {{ margin:8px 0; color:#CBD5E1; font-size:13px; }}
    .status-card small {{ color:var(--muted); }}
    .status-ok {{ border-color:rgba(16,185,129,.35); }}
    .status-warn {{ border-color:rgba(245,158,11,.42); }}
    .status-bad {{ border-color:rgba(239,68,68,.46); }}
    .scope-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .scope-card {{ border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:14px; background:rgba(15,23,42,.42); }}
    .scope-card span {{ display:block; color:#A5B4FC; font-size:13px; font-weight:800; margin-bottom:7px; }}
    .scope-card p, .limit-list p {{ margin:0; color:#CBD5E1; line-height:1.75; font-size:13px; }}
    .limit-list {{ display:grid; gap:8px; margin-top:12px; border:1px solid rgba(245,158,11,.22); border-radius:18px; padding:14px; background:rgba(245,158,11,.07); }}
    @media (max-width:1024px) {{
      .kpi-grid, .two-col, .insight-grid, .lens-grid, .scope-grid, .audit-summary {{ grid-template-columns:1fr; }}
      .dashboard {{ width:min(100% - 20px, 1480px); padding-top:14px; }}
    }}
    @media (min-width:1024px) {{
      .hero > .flex {{ flex-direction:row; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; }}
    }}
  </style>
</head>
<body>
  <div class="dashboard">
    <header class="hero glass-card">
      <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 relative z-10">
        <div>
          <h1>二次元游戏行业与重点厂商舆情{esc(report_kind)}看板</h1>
          <p>统计周期：最近 {lookback_days} 天 / {esc(start_label)} - {esc(report_date)}</p>
        </div>
        <div class="flex flex-col items-start lg:items-end gap-2">
          <span class="module-sub">米哈游 / 库洛 / 二游大盘</span>
        </div>
      </div>
      <div class="kpi-grid relative z-10">
        <section class="kpi glass-card"><span class="label"><i data-lucide="link"></i>带 URL 线索</span><div class="value">{core_count}</div><div class="delta">AI 返回的可点击来源，仍需复核</div></section>
        <section class="kpi glass-card"><span class="label"><i data-lucide="messages-square"></i>辅助样本</span><div class="value">{auxiliary_count}</div><div class="delta">无 URL 但具体的 AI 观察</div></section>
        <section class="kpi glass-card"><span class="label"><i data-lucide="boxes"></i>命中游戏</span><div class="value">{hit_game_count}</div><div class="delta">关注矩阵 {watch_game_count} 款，未命中 {unhit_game_count} 款</div></section>
        <section class="kpi glass-card warning"><span class="label"><i data-lucide="triangle-alert"></i>中高风险线索</span><div class="value">{medium_high_count}</div><div class="delta">medium / high 风险事件数</div></section>
      </div>
    </header>

    <main class="grid gap-4 mt-4">
      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="list-checks"></i>{esc(period_label)}关键结论</h2><span class="module-sub">先看本轮最值得同步的变化、风险与证据边界</span></div>
        <ul class="conclusion-list">{key_items}</ul>
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="boxes"></i>关注矩阵周度覆盖</h2><span class="module-sub">展示关注矩阵命中、URL 线索与辅助样本，不做逐个硬写</span></div>
        {hit_games}
        {parse_note}
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="compass"></i>赛道新闻与案例</h2><span class="module-sub">展示休闲种田、宠物养成、搜打撤、动作竞技、开放世界/3A 化等方向的具体内容</span></div>
        {sector_cases}
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="target"></i>重点产品/游戏命中</h2><span class="module-sub">只展示最近 {lookback_days} 天有实际公开信息或社区讨论的游戏</span></div>
        {hit_game_chips(records)}
      </section>

      <section class="company-block">
        <div class="module-head"><h2><i data-lucide="building-2"></i>米哈游 / 库洛重点事件</h2><span class="module-sub">按社区讨论、版本更新、新闻公告拆分查看公司级观察</span></div>
        <div class="two-col company-section">
          {company_focus_card("米哈游", records, "mihoyo")}
          {company_focus_card("库洛", records, "kuro")}
        </div>
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="radar"></i>其他二游与竞品动态</h2><span class="module-sub">补充非米哈游/库洛的二游内容，让周报不只围绕重点厂商</span></div>
        {non_key_cases}
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="table-2"></i>按游戏证据表</h2><span class="module-sub">带 URL 线索优先；标题、时间与玩家反馈需结合来源页面复核</span></div>
        <div class="filter-bar">
          <button class="filter-btn active" data-filter="全部">全部</button>
          <button class="filter-btn" data-filter="米哈游">米哈游</button>
          <button class="filter-btn" data-filter="库洛">库洛</button>
          <button class="filter-btn" data-filter="其他">其他</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>游戏 / 厂商</th><th>事件简述</th><th>舆情级别</th><th>主发源地 / 平台</th><th>采样链接</th></tr></thead>
            <tbody id="evidenceBody">{evidence_rows(records)}</tbody>
          </table>
        </div>
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="sparkles"></i>玩家倾向变化 & 玩家建议</h2><span class="module-sub">展示本轮倾向结构、触发原因、关联游戏与具体玩家建议</span></div>
        <div class="insight-grid">{insight_cards(records)}</div>
      </section>

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="scan-search"></i>待验证线索</h2><span class="module-sub">传闻、爆料、公关隐患、版本风向，需二次核查</span></div>
        <div class="rumor-grid">{pending_cards(pending)}</div>
      </section>

      {platform_status_section}

      <section class="module glass-card">
        <div class="module-head"><h2><i data-lucide="shield-question"></i>信源范围与限制</h2><span class="module-sub">帮助读者判断本轮报告可以信到什么程度</span></div>
        {source_scope}
      </section>
    </main>
  </div>

  <script>
    const chartPayload = {chart};
    const chartEl = document.getElementById('trendChart');
    if (window.echarts && chartEl) {{
      const chart = echarts.init(chartEl);
      chart.setOption({{
        backgroundColor: 'transparent',
        tooltip: {{ trigger: 'axis' }},
        legend: {{ textStyle: {{ color: '#CBD5E1' }}, top: 0 }},
        grid: {{ left: 36, right: 24, top: 48, bottom: 34 }},
        xAxis: {{ type: 'category', data: chartPayload.labels, axisLabel: {{ color: '#94A3B8' }}, axisLine: {{ lineStyle: {{ color: 'rgba(148,163,184,.25)' }} }} }},
        yAxis: {{ type: 'value', axisLabel: {{ color: '#94A3B8' }}, splitLine: {{ lineStyle: {{ color: 'rgba(148,163,184,.12)' }} }} }},
        series: [
          {{ name:'讨论量', type:'line', smooth:true, data:chartPayload.total, areaStyle:{{ color:'rgba(59,130,246,.18)' }}, lineStyle:{{ color:'#3B82F6', width:3 }}, itemStyle:{{ color:'#3B82F6' }} }},
          {{ name:'正面情绪', type:'line', smooth:true, data:chartPayload.positive, lineStyle:{{ color:'#10B981', width:2 }}, itemStyle:{{ color:'#10B981' }} }},
          {{ name:'负面情绪', type:'line', smooth:true, data:chartPayload.negative, lineStyle:{{ color:'#EF4444', width:2 }}, itemStyle:{{ color:'#EF4444' }} }}
        ]
      }});
      window.addEventListener('resize', () => chart.resize());
    }} else if (chartEl) {{
      chartEl.innerHTML = '<div class="empty">图表库未加载，保留数据表展示。</div>';
    }}

    document.querySelectorAll('.filter-btn').forEach((button) => {{
      button.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        const filter = button.dataset.filter;
        document.querySelectorAll('#evidenceBody tr[data-company]').forEach((row) => {{
          row.style.display = filter === '全部' || row.dataset.company === filter ? '' : 'none';
        }});
      }});
    }});

    if (window.lucide) {{
      window.lucide.createIcons();
    }}
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", help="Raw Web AI JSON files or directories")
    parser.add_argument("--output", "-o", default="company_daily_report.html")
    parser.add_argument("--title", default="二次元游戏行业与重点厂商舆情情报看板")
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--report-mode", choices=["daily", "weekly"], default="")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--normalized-output", default="")
    parser.add_argument("--allow-no-url-evidence", action="store_true", help="Display URL-less model outputs as auxiliary samples for exploratory runs")
    parser.add_argument("--show-platform-status", action="store_true", help="Show platform collection/debug status cards in the HTML report")
    args = parser.parse_args()

    evidence, pending, errors, platform_status, metadata = load_outputs(collect_files(args.inputs), args.allow_no_url_evidence) if args.inputs else ([], [], [], [], {})
    if args.report_mode:
        metadata["report_mode"] = args.report_mode
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_html(
            evidence,
            pending,
            errors,
            platform_status,
            metadata,
            args.title,
            args.report_date,
            args.lookback_days,
            args.show_platform_status,
        ),
        encoding="utf-8",
    )

    normalized = args.normalized_output or str(output.with_name("normalized_company_evidence.json"))
    Path(normalized).write_text(
        json.dumps(
            {
                "evidence": evidence,
                "pending_leads": pending,
                "errors": errors,
                "platform_status": platform_status,
                "report_metadata": metadata,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "normalized_output": normalized,
                "evidence": len(evidence),
                "pending_leads": len(pending),
                "errors": len(errors),
                "platform_status": len(platform_status),
                "watch_game_count": metadata.get("watch_game_count"),
                "hit_game_count": metadata.get("hit_game_count"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
