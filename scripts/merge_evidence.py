#!/usr/bin/env python3
"""Merge candidate evidence JSON files into a deduplicated evidence pool."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"spm", "from", "source", "share_source"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def load_records(path: str) -> list[dict[str, Any]]:
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):
        return data
    for key in ("evidence", "results", "items", "records"):
        if isinstance(data.get(key), list):
            return data[key]
    return [data]


def evidence_level(record: dict[str, Any]) -> str:
    url = (record.get("url") or "").strip()
    access = record.get("access_status") or "unknown"
    source_type = record.get("source_type") or "search_result"
    if not url:
        return "secondary_only"
    if access in {"blocked_login", "forbidden_403", "captcha", "paywalled"}:
        return "excluded"
    if source_type in {"original_post", "comment", "official", "user_supplied_url"} and access in {"accessible", "unknown"}:
        return "core"
    if source_type in {"search_result", "web_ai_summary"}:
        return "supporting"
    return "supporting"


def default_confidence(level: str, access: str) -> float:
    if level == "core":
        return 0.85
    if level == "supporting":
        return 0.65 if access != "search_snippet_only" else 0.55
    if level == "secondary_only":
        return 0.35
    return 0.1


def merge(paths: list[str]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    no_url_records: list[dict[str, Any]] = []
    retrieved_at = date.today().isoformat()

    for path in paths:
        for record in load_records(path):
            item = dict(record)
            item.setdefault("retrieved_at", retrieved_at)
            item.setdefault("access_status", "unknown" if item.get("url") else "no_url")
            item.setdefault("source_type", "search_result")
            item["evidence_level"] = evidence_level(item)
            item.setdefault("confidence", default_confidence(item["evidence_level"], item["access_status"]))
            item.setdefault("limitations", "")

            url = (item.get("url") or "").strip()
            if not url:
                no_url_records.append(item)
                continue
            key = normalize_url(url)
            item["url"] = key
            if key not in merged or item["confidence"] > merged[key].get("confidence", 0):
                merged[key] = item

    output = list(merged.values()) + no_url_records
    for index, item in enumerate(output, start=1):
        item["evidence_id"] = item.get("evidence_id") or f"ev_{index:03d}"
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Candidate evidence JSON files")
    parser.add_argument("--output", "-o", default="evidence_pool.json")
    args = parser.parse_args()

    pool = merge(args.inputs)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(pool, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": args.output, "records": len(pool)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
