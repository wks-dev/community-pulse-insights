#!/usr/bin/env python3
"""Tag evidence with an OpenAI-compatible API, or emit a manual prompt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import request


SYSTEM_PROMPT = """You tag public game-community evidence. Return strict JSON only.
For each evidence item, output: evidence_id, sentiment, topic, player_intent,
risk_level, actionable, summary, evidence_quote_or_snippet, confidence.
Do not fabricate quotes. Lower confidence for search snippets, inaccessible pages,
or Web AI summaries. URL-less evidence is secondary only."""


def load_pool(path: str) -> list[dict[str, Any]]:
    data = json.load(open(path, encoding="utf-8"))
    return data if isinstance(data, list) else data.get("evidence", [])


def build_prompt(pool: list[dict[str, Any]]) -> str:
    return (
        "Tag the following evidence according to the schema. Return a JSON array only.\n\n"
        + json.dumps(pool, ensure_ascii=False, indent=2)
    )


def call_api(prompt: str) -> str:
    api_key = os.getenv("EXTERNAL_AI_API_KEY")
    base_url = os.getenv("EXTERNAL_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("EXTERNAL_AI_MODEL", "gpt-4.1-mini")
    if not api_key:
        raise RuntimeError("Missing EXTERNAL_AI_API_KEY")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def write_manual_prompt(prompt: str, out_dir: str) -> Path:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / "tagging_prompt.md"
    target.write_text(
        "# Manual Tagging Prompt\n\n"
        "No `EXTERNAL_AI_API_KEY` was found. Submit the prompt below to an OpenAI-compatible model, then save the returned JSON as `tagged_evidence.json`.\n\n"
        "```text\n"
        f"{SYSTEM_PROMPT}\n\n{prompt}\n"
        "```\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_pool", help="Path to evidence_pool.json")
    parser.add_argument("--output", "-o", default="tagged_evidence.json")
    parser.add_argument("--prompt-dir", default="prompts")
    args = parser.parse_args()

    pool = load_pool(args.evidence_pool)
    prompt = build_prompt(pool)
    if not os.getenv("EXTERNAL_AI_API_KEY"):
        prompt_path = write_manual_prompt(prompt, args.prompt_dir)
        print(json.dumps({"status": "no_api_key", "prompt": str(prompt_path)}, ensure_ascii=False, indent=2))
        return 0

    content = call_api(prompt)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"raw_model_output": content}
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(parsed, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": "tagged", "output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
