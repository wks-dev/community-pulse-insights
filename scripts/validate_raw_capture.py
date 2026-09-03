#!/usr/bin/env python3
"""Validate raw browser captures before structural parsing.

This is intentionally read-only. It reports whether a raw envelope contains a
clean current AI answer or only a page shell/prompt echo. It never promotes a
capture and never edits the raw file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from skill_metadata import COLLECTOR_VERSION, SKILL_VERSION


PAGE_SHELL_MARKERS = (
    "AUTOMATION_MARKER",
    "COLLECT_RUN_ID=",
    "PROMPT_ID=",
    "输出必须是严格 JSON",
    "搜索",
    "收藏",
    "历史",
    "深度思考",
    "内容由AI生成",
)

STRUCTURED_FRAGMENT_MARKERS = (
    '"game_name"',
    '"matched_alias"',
    '"product_tier"',
    '"game_status"',
    '"source_file"',
    "product_tier",
    "game_status",
)


def collect_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {"response_text": json.dumps(data, ensure_ascii=False)}


def validate(path: Path) -> dict[str, Any]:
    try:
        data = read_json(path)
    except Exception as exc:
        return {"file": str(path), "valid": False, "quality": "invalid_json", "error": str(exc)}

    text = str(data.get("response_text") or "").strip()
    marker_echo = "AUTOMATION_MARKER" in text or "COLLECT_RUN_ID=" in text or "PROMPT_ID=" in text
    shell_hits = sum(1 for marker in PAGE_SHELL_MARKERS if marker in text)
    fragment_hits = sum(1 for marker in STRUCTURED_FRAGMENT_MARKERS if marker in text)
    explicit_failure = data.get("send_confirmed") is False or data.get("prompt_id_confirmed") is False
    incomplete = data.get("response_started") is False or data.get("response_completed") is False
    quality = "clean_candidate"
    if explicit_failure or incomplete:
        quality = "collection_failed"
    elif not text:
        quality = "empty_response"
    elif marker_echo and fragment_hits >= 2:
        quality = "prompt_echo_with_structured_fragments"
    elif marker_echo and shell_hits >= 3:
        quality = "page_shell_or_prompt_echo"
    elif marker_echo:
        quality = "prompt_echo_present"
    elif fragment_hits >= 3:
        quality = "structured_fragment_pollution"

    valid = quality == "clean_candidate"
    return {
        "file": str(path),
        "ai_tool": data.get("ai_tool", ""),
        "prompt_id": data.get("prompt_id", ""),
        "status": data.get("status", ""),
        "response_chars": len(text),
        "send_confirmed": data.get("send_confirmed"),
        "prompt_id_confirmed": data.get("prompt_id_confirmed"),
        "response_started": data.get("response_started"),
        "response_completed": data.get("response_completed"),
        "marker_echo": marker_echo,
        "page_shell_marker_hits": shell_hits,
        "structured_fragment_hits": fragment_hits,
        "quality": quality,
        "valid": valid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Raw JSON files or directories")
    parser.add_argument("--strict", action="store_true", help="Return exit code 1 when any capture is not clean")
    args = parser.parse_args()
    results = [validate(path) for path in collect_files(args.inputs)]
    payload = {
        "skill_version": SKILL_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "files": results,
        "valid_count": sum(1 for item in results if item.get("valid")),
        "invalid_count": sum(1 for item in results if not item.get("valid")),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if args.strict and payload["invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
