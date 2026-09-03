#!/usr/bin/env python3
"""Load a game list workbook/CSV into normalized JSON records."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


HEADER_ALIASES = {
    "game_name": {"game", "game_name", "游戏", "游戏名", "游戏名称", "中文名", "名称", "name"},
    "english_name": {"english_name", "英文名", "en", "english"},
    "aliases": {"alias", "aliases", "别名", "别称", "关键词", "keywords"},
    "platforms": {"platform", "platforms", "平台"},
    "enabled": {"enabled", "启用", "是否启用"},
    "priority": {"priority", "优先级"},
    "notes": {"notes", "备注", "说明"},
}


def clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def looks_like_header(row: list[str]) -> bool:
    values = {cell.strip().lower() for cell in row if cell.strip()}
    known = set().union(*(aliases for aliases in HEADER_ALIASES.values()))
    return bool(values & known)


def header_map(row: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for idx, cell in enumerate(row):
        folded = cell.strip().lower()
        for field, aliases in HEADER_ALIASES.items():
            if folded in aliases:
                mapping[idx] = field
    return mapping


def split_aliases(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，、;/|]+", value or "") if part.strip()]


def truthy(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "n", "否", "停用", "disabled"}


def normalize_records(rows: list[list[str]], sheet_name: str = "") -> list[dict[str, Any]]:
    rows = [[clean(cell) for cell in row] for row in rows]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []

    use_header = looks_like_header(rows[0])
    mapping = header_map(rows[0]) if use_header else {}
    data_rows = rows[1:] if use_header else rows
    records = []

    for row in data_rows:
        if not any(row):
            continue
        aliases: list[str] = []
        platforms: list[str] = []
        enabled = True
        priority = ""
        notes = ""

        if mapping:
            primary = ""
            for idx, field in mapping.items():
                value = row[idx] if idx < len(row) else ""
                if field in {"game_name", "english_name"} and value:
                    aliases.append(value)
                    primary = primary or value
                elif field == "aliases":
                    aliases.extend(split_aliases(value))
                elif field == "platforms":
                    platforms.extend(split_aliases(value))
                elif field == "enabled":
                    enabled = truthy(value)
                elif field == "priority":
                    priority = value
                elif field == "notes":
                    notes = value
        else:
            aliases.extend(cell for cell in row if cell)

        deduped_aliases = list(dict.fromkeys(alias for alias in aliases if alias))
        if not deduped_aliases or not enabled:
            continue
        records.append(
            {
                "game_id": f"game_{len(records) + 1:03d}",
                "game_name": deduped_aliases[0],
                "aliases": deduped_aliases,
                "platforms": list(dict.fromkeys(platforms)),
                "priority": priority,
                "notes": notes,
                "source_sheet": sheet_name,
            }
        )
    return records


def read_spreadsheet(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter=delimiter))
        return normalize_records(rows)

    if suffix == ".xls":
        import pandas as pd

        workbook = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        records: list[dict[str, Any]] = []
        for sheet_name, frame in workbook.items():
            rows = frame.fillna("").astype(str).values.tolist()
            records.extend(normalize_records(rows, str(sheet_name)))
    else:
        import openpyxl

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        records = []
        for sheet in workbook.worksheets:
            rows = [[clean(value) for value in row] for row in sheet.iter_rows(values_only=True)]
            records.extend(normalize_records(rows, sheet.title))

    for idx, record in enumerate(records, start=1):
        record["game_id"] = f"game_{idx:03d}"
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list", help="Path to .xlsx/.xls/.csv/.tsv game list")
    parser.add_argument("--output", "-o", default="game_list.json")
    args = parser.parse_args()

    records = read_spreadsheet(Path(args.game_list))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump({"games": records, "count": len(records)}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": args.output, "games": len(records)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
