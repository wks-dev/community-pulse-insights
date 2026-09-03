#!/usr/bin/env python3
"""Audit raw Web AI captures before structural parsing.

This stage-1 gate answers a narrower question than the structurer: did the
raw file contain a real current AI answer, or only a successful-looking
capture such as a prompt echo, page shell, refusal, history mix, or fragment?
It is deliberately read-only for raw files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from skill_metadata import COLLECTOR_VERSION, SKILL_VERSION


URL_RE = re.compile(r"https?://[^\s\]）)\"'，。；、<>]+", re.IGNORECASE)

PROMPT_MARKERS = (
    "AUTOMATION_MARKER",
    "COLLECT_RUN_ID=",
    "PROMPT_ID=",
)

PROMPT_INSTRUCTION_MARKERS = (
    "当前 Web AI 工具",
    "当前 AI 工具",
    "工具身份防漂移",
    "本轮唯一检索对象",
    "禁止把任何 AI 工具",
    "输出必须是严格 JSON",
    "硬性规则",
    "请检索最近",
    "你是游戏行业社区舆情检索助手",
    "你是二次元游戏行业周报扩展检索助手",
    "游戏类型观察口径",
    "关注矩阵",
    "不写入 evidence",
)

SCHEMA_MARKERS = (
    '"game_name"',
    '"matched_alias"',
    '"product_tier"',
    '"game_status"',
    '"source_ai"',
    '"evidence_level"',
    '"pending_leads"',
    '"not_hit_games"',
    "core_evidence | auxiliary_sample | pending_lead",
    "accessible | search_snippet_only",
    "YYYY-MM-DD",
    "https://...",
    "帖子/视频/问答/新闻/公告标题",
    "只基于证据的一句话说明",
    "关注矩阵中的游戏名",
)

PAGE_SHELL_MARKERS = (
    "新建对话",
    "我的空间",
    "智能体",
    "对话历史",
    "最近对话",
    "向千问提问",
    "任务助理",
    "PPT创作",
    "AI生图",
    "AI生视频",
    "下载",
    "工具区",
    "请输入你的问题",
    "API 服务",
    "应用中心",
    "模型选择",
    "下载电脑端",
    "安装电脑版",
    "内容由AI生成",
    "查看使用规则",
    "深度思考",
    "知识库",
)

HISTORY_MIX_MARKERS = (
    "最近对话",
    "对话历史",
    "历史记录",
    "今天",
    "昨天",
    "之前的回答",
    "新分组",
    "提炼文档关键信息",
    "AUTOMATION.txt",
    "米哈游7月",
    "千问适配器重测",
)

AI_PRODUCT_MARKERS = (
    "千问 - 阿里旗下全能AI助手",
    "千问-阿里 AI 助手",
    "阿里 AI 助手",
    "Qwen",
    "通义千问",
    "API 服务",
    "豆包",
    "元宝",
    "文心一言",
    "Gemini",
    "Grok",
)

REFUSAL_MARKERS = (
    "无法为你提供",
    "不能为你提供",
    "无法协助",
    "不能协助",
    "不支持此类请求",
    "网络安全",
    "翻墙",
    "合规AI助手",
    "严格遵守国家网络管理",
    "违法行为",
)

GAME_MARKERS = (
    "原神",
    "Genshin",
    "绝区零",
    "Zenless",
    "ZZZ",
    "崩坏",
    "星穹铁道",
    "Star Rail",
    "Honkai",
    "未定事件簿",
    "Tears of Themis",
    "因缘精灵",
    "Nexus Anima",
    "星布谷地",
    "Petit Planet",
    "Varsapura",
    "鸣潮",
    "Wuthering Waves",
    "战双",
    "Punishing",
    "幻塔",
    "Tower of Fantasy",
    "恋与深空",
    "Love and Deepspace",
    "Love & Deepspace",
    "NIKKE",
    "FGO",
    "碧蓝航线",
    "Azur Lane",
    "明日方舟",
    "Arknights",
    "异环",
    "Neverness",
    "无限大",
    "Ananta",
    "蓝色星原",
    "Azure Promilia",
    "尘白禁区",
    "Snowbreak",
    "重返未来",
    "Reverse: 1999",
    "少女前线",
    "Girls' Frontline",
    "赛马娘",
    "Uma Musume",
    "动物森友会",
    "Animal Crossing",
    "心动小镇",
    "Heartopia",
    "蔚蓝档案",
    "Blue Archive",
)

PLAYER_OR_EVENT_MARKERS = (
    "玩家",
    "舆情",
    "社区",
    "讨论",
    "评论",
    "帖子",
    "笔记",
    "问答",
    "版本",
    "活动",
    "角色",
    "剧情",
    "抽卡",
    "付费",
    "氪金",
    "退坑",
    "回流",
    "入坑",
    "观望",
    "争议",
    "优化",
    "建议",
    "风险",
    "平台",
    "标题或事件",
    "玩家具体意见",
    "风险等级",
    "URL",
    "no_url",
    "待核验",
)

INCOMPLETE_ENDINGS = (
    '"evidence":',
    '"evidence": [',
    "| :--- | :--- | :--",
    "以下是整理出的8条重要内容：",
)

CSV_FIELDS = (
    "ai_tool",
    "prompt_id",
    "status",
    "capture_mode",
    "answer_confirmed",
    "needs_human_review",
    "candidate_score",
    "response_chars",
    "valid_answer",
    "answer_quality",
    "invalid_reason",
    "is_prompt_echo",
    "is_page_shell",
    "is_refusal",
    "is_history_mix",
    "is_incomplete_answer",
    "prompt_marker_count",
    "schema_marker_count",
    "game_signal_count",
    "url_count",
    "source_file",
)


def clean_text(value: Any) -> str:
    return (
        str(value or "")
        .replace("\u00a0", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )


def collect_files(inputs: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def read_json_or_text(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except Exception:
        return {"status": "raw_text", "response_text": text}
    if isinstance(data, dict):
        return data
    return {"status": "raw_json", "response_text": json.dumps(data, ensure_ascii=False)}


def count_markers(text: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker and marker in text)


def real_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).strip().strip(".,;，。；、")
        if "https://..." in url:
            continue
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            continue
        if parts.netloc.lower() in {"zhihu.co", "www.zhihu.co"}:
            continue
        urls.append(url)
    return urls


def looks_like_prompt_echo(text: str, prompt_marker_count: int, schema_marker_count: int) -> bool:
    instruction_count = count_markers(text, PROMPT_INSTRUCTION_MARKERS)
    if prompt_marker_count and (instruction_count >= 1 or schema_marker_count >= 2):
        return True
    if instruction_count >= 3 and schema_marker_count >= 2:
        return True
    if text.lstrip().startswith(("你是游戏行业社区舆情检索助手", "你是二次元游戏行业周报扩展检索助手")):
        return True
    return False


def looks_like_page_shell(text: str, page_shell_count: int) -> bool:
    if page_shell_count >= 5:
        return True
    if page_shell_count >= 3 and len(text) > 2000:
        return True
    return False


def looks_like_history_mix(text: str, history_count: int) -> bool:
    if history_count >= 3:
        return True
    return history_count >= 2 and len(text) > 1000


def looks_incomplete(data: dict[str, Any], text: str) -> bool:
    capture_mode = str(data.get("capture_mode") or "").lower()
    stripped = text.strip()
    if "candidate" in capture_mode and len(stripped) >= 180 and not stripped.endswith(INCOMPLETE_ENDINGS):
        return False
    if data.get("response_started") is False or data.get("response_completed") is False:
        return True
    if len(stripped) < 260 and any(marker in stripped for marker in INCOMPLETE_ENDINGS):
        return True
    if len(stripped) < 260 and stripped.count("|") >= 8 and "玩家具体意见" in stripped:
        return True
    if stripped.endswith(INCOMPLETE_ENDINGS):
        return True
    return False


def has_answer_content(game_signal_count: int, player_signal_count: int, url_count: int, text: str) -> bool:
    if game_signal_count <= 0:
        return False
    if url_count > 0:
        return True
    if player_signal_count >= 3:
        return True
    if "no_url" in text or "待核验" in text or "URL：" in text or "URL:" in text:
        return True
    return False


def invalid_reason_for(
    *,
    data: dict[str, Any],
    text: str,
    is_prompt_echo: bool,
    is_page_shell: bool,
    is_refusal: bool,
    is_history_mix: bool,
    is_incomplete_answer: bool,
    game_signal_count: int,
    player_signal_count: int,
    url_count: int,
) -> str:
    status = str(data.get("status") or "").lower()
    if status == "error" or data.get("send_confirmed") is False or data.get("prompt_id_confirmed") is False:
        return "collection_failed_or_prompt_unconfirmed"
    if not text.strip():
        return "empty_response"
    reasons: list[str] = []
    if is_prompt_echo:
        reasons.append("prompt_echo")
    if is_refusal:
        reasons.append("refusal")
    if is_history_mix:
        reasons.append("history_mix")
    if is_page_shell:
        reasons.append("page_shell")
    if is_incomplete_answer:
        reasons.append("incomplete_answer")
    if reasons:
        return "+".join(reasons)
    if game_signal_count <= 0:
        return "no_game_signal"
    if not has_answer_content(game_signal_count, player_signal_count, url_count, text):
        return "no_answer_content_signal"
    return ""


def answer_quality_for(data: dict[str, Any], text: str, url_count: int, player_signal_count: int) -> str:
    capture_quality = str(data.get("capture_quality") or "").lower()
    if "candidate" in str(data.get("capture_mode") or "").lower():
        return "candidate"
    if capture_quality == "weak" or url_count == 0:
        return "weak"
    if url_count >= 2 or len(text) >= 1200 or player_signal_count >= 5:
        return "strong"
    return "normal"


def audit_file(path: Path) -> dict[str, Any]:
    try:
        data = read_json_or_text(path)
    except Exception as exc:
        return {
            "ai_tool": "",
            "prompt_id": path.stem,
            "status": "invalid_json",
            "capture_mode": "",
            "answer_confirmed": False,
            "needs_human_review": False,
            "candidate_score": "",
            "response_chars": 0,
            "valid_answer": False,
            "answer_quality": "invalid",
            "invalid_reason": f"invalid_json:{exc}",
            "is_prompt_echo": False,
            "is_page_shell": False,
            "is_refusal": False,
            "is_history_mix": False,
            "is_incomplete_answer": False,
            "prompt_marker_count": 0,
            "schema_marker_count": 0,
            "game_signal_count": 0,
            "url_count": 0,
            "source_file": str(path),
        }

    text = clean_text(data.get("response_text") or "")
    prompt_marker_count = count_markers(text, PROMPT_MARKERS)
    schema_marker_count = count_markers(text, SCHEMA_MARKERS)
    game_signal_count = count_markers(text, GAME_MARKERS)
    player_signal_count = count_markers(text, PLAYER_OR_EVENT_MARKERS)
    url_count = len(real_urls(text))
    page_shell_count = count_markers(text, PAGE_SHELL_MARKERS)
    history_count = count_markers(text, HISTORY_MIX_MARKERS)
    is_refusal = count_markers(text, REFUSAL_MARKERS) > 0
    is_prompt_echo = looks_like_prompt_echo(text, prompt_marker_count, schema_marker_count)
    is_page_shell = looks_like_page_shell(text, page_shell_count)
    is_history_mix = looks_like_history_mix(text, history_count)
    is_incomplete_answer = looks_incomplete(data, text)

    reason = invalid_reason_for(
        data=data,
        text=text,
        is_prompt_echo=is_prompt_echo,
        is_page_shell=is_page_shell,
        is_refusal=is_refusal,
        is_history_mix=is_history_mix,
        is_incomplete_answer=is_incomplete_answer,
        game_signal_count=game_signal_count,
        player_signal_count=player_signal_count,
        url_count=url_count,
    )
    valid_answer = not reason
    return {
        "ai_tool": data.get("ai_tool", ""),
        "prompt_id": data.get("prompt_id", path.stem),
        "status": data.get("status", ""),
        "capture_mode": data.get("capture_mode", ""),
        "answer_confirmed": data.get("answer_confirmed", ""),
        "needs_human_review": data.get("needs_human_review", ""),
        "candidate_score": data.get("candidate_score", ""),
        "response_chars": len(text),
        "valid_answer": valid_answer,
        "answer_quality": answer_quality_for(data, text, url_count, player_signal_count) if valid_answer else "invalid",
        "invalid_reason": reason,
        "is_prompt_echo": is_prompt_echo,
        "is_page_shell": is_page_shell,
        "is_refusal": is_refusal,
        "is_history_mix": is_history_mix,
        "is_incomplete_answer": is_incomplete_answer,
        "prompt_marker_count": prompt_marker_count,
        "schema_marker_count": schema_marker_count,
        "game_signal_count": game_signal_count,
        "url_count": url_count,
        "source_file": str(path),
    }


def audit_files(paths: list[str | Path]) -> list[dict[str, Any]]:
    return [audit_file(path) for path in collect_files(paths)]


def summarize_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ai: dict[str, dict[str, Any]] = {}
    for row in rows:
        tool = str(row.get("ai_tool") or "unknown")
        bucket = by_ai.setdefault(
            tool,
            {
                "valid": 0,
                "invalid": 0,
                "qualities": {},
                "invalid_reasons": {},
            },
        )
        if row.get("valid_answer"):
            bucket["valid"] += 1
            quality = str(row.get("answer_quality") or "unknown")
            bucket["qualities"][quality] = bucket["qualities"].get(quality, 0) + 1
        else:
            bucket["invalid"] += 1
            reason = str(row.get("invalid_reason") or "unknown")
            bucket["invalid_reasons"][reason] = bucket["invalid_reasons"].get(reason, 0) + 1
    return {
        "valid_answer_count": sum(1 for row in rows if row.get("valid_answer")),
        "invalid_answer_count": sum(1 for row in rows if not row.get("valid_answer")),
        "valid_answer_by_ai": by_ai,
    }


def write_audit_outputs(rows: list[dict[str, Any]], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "raw_quality_audit.json"
    csv_path = output_dir / "raw_quality_audit.csv"
    payload = {
        "skill_version": SKILL_VERSION,
        "collector_version": COLLECTOR_VERSION,
        **summarize_audit(rows),
        "files": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return {"json": str(json_path), "csv": str(csv_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Raw JSON files or directories")
    parser.add_argument("--output-dir", default="", help="Directory for raw_quality_audit.json/csv")
    parser.add_argument("--strict", action="store_true", help="Return 1 if any raw file is not a valid answer")
    args = parser.parse_args()

    rows = audit_files(args.inputs)
    summary = summarize_audit(rows)
    payload = {
        "skill_version": SKILL_VERSION,
        "collector_version": COLLECTOR_VERSION,
        **summary,
        "files": rows,
    }
    if args.output_dir:
        payload["outputs"] = write_audit_outputs(rows, Path(args.output_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if args.strict and summary["invalid_answer_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
