#!/usr/bin/env python3
"""Merge daily AI/search output JSON files into normalized evidence records."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_") and k not in {"spm", "from", "source"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def load_records(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):
        return data, []
    return data.get("evidence", data.get("records", [])), data.get("pending_leads", [])


def evidence_level(record: dict[str, Any]) -> str:
    url = record.get("url") or ""
    status = record.get("access_status") or "unknown"
    if not url:
        return "secondary_only"
    if status in {"blocked_login", "forbidden_403", "captcha", "paywalled"}:
        return "excluded"
    if status in {"accessible", "unknown"}:
        return "core"
    return "supporting"


def merge(paths: list[str]) -> dict[str, Any]:
    seen: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    today = date.today().isoformat()
    for path in paths:
        evidence, leads = load_records(path)
        pending.extend(leads)
        for item in evidence:
            row = dict(item)
            row.setdefault("retrieved_at", today)
            row.setdefault("access_status", "unknown" if row.get("url") else "no_url")
            row["evidence_level"] = evidence_level(row)
            row.setdefault("limitations", "")
            url = normalize_url(row.get("url") or "")
            key = url or f"no_url::{len(pending)}::{row.get('summary')}"
            if url:
                row["url"] = url
            if key not in seen:
                seen[key] = row
    records = list(seen.values())
    for idx, item in enumerate(records, start=1):
        item.setdefault("evidence_id", f"ev_{idx:04d}")
    return {"evidence": records, "pending_leads": pending, "count": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="AI output JSON files")
    parser.add_argument("--output", "-o", default="daily_evidence.json")
    args = parser.parse_args()

    result = merge(args.inputs)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": args.output, "evidence": result["count"], "pending_leads": len(result["pending_leads"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
