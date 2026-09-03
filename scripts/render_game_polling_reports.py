#!/usr/bin/env python3
"""Render per-game and combined HTML reports from game-list polling outputs."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(value: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(value or "game")).strip("_")
    return text[:80] or "game"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_") and k not in {"spm", "from", "source"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def collect_json_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.name not in {"game_list.json", "prompt_pack.json", "submit_all.json"}))
        elif path.exists():
            files.append(path)
    return files


def normalize_record(item: dict[str, Any], source: dict[str, Any], fallback_game_id: str = "", fallback_game_name: str = "") -> dict[str, Any]:
    url = normalize_url(item.get("url") or item.get("link") or "")
    access_status = item.get("access_status") or ("unknown" if url else "no_url")
    evidence_level = "core" if url and access_status not in {"blocked_login", "forbidden_403", "captcha", "paywalled", "no_url"} else "secondary_only"
    return {
        "game_id": item.get("game_id") or source.get("game_id") or fallback_game_id,
        "game_name": item.get("game_name") or source.get("game_name") or fallback_game_name,
        "aliases": item.get("aliases") or source.get("aliases") or [],
        "source_ai": item.get("source_ai") or source.get("ai_tool") or source.get("source_ai") or "",
        "platform": item.get("source_platform") or item.get("platform") or item.get("platform_focus") or source.get("platform_focus") or "",
        "title": item.get("title") or item.get("event_or_discussion") or item.get("summary") or "",
        "url": url,
        "published_at": item.get("published_at") or "",
        "event_type": item.get("event_type") or item.get("topic") or item.get("event_or_discussion") or "其他",
        "player_tendency": item.get("player_tendency") or item.get("player_sentiment") or item.get("sentiment") or "",
        "player_intent": item.get("player_intent") or "",
        "specific_player_opinions": item.get("specific_player_opinions") or "",
        "sentiment": item.get("sentiment") or item.get("player_sentiment") or "",
        "risk_level": str(item.get("risk_level") or "low").lower(),
        "snippet": item.get("snippet") or item.get("evidence_quote_or_snippet") or "",
        "summary": item.get("summary") or item.get("event_or_discussion") or "",
        "why_watch": item.get("why_watch") or item.get("evidence_support") or "",
        "access_status": access_status,
        "evidence_level": evidence_level,
        "limitations": item.get("limitations") or "",
    }


def load_outputs(files: list[Path], games: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    game_by_id = {game["game_id"]: game for game in games}
    seen: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    for path in files:
        try:
            data = load_json(path)
        except Exception:
            pending.append({"lead": f"无法解析 JSON: {path}", "reason": "parse_error", "source_file": str(path)})
            continue

        containers = data if isinstance(data, list) else [data]
        for container in containers:
            if not isinstance(container, dict):
                continue
            fallback_game_id = str(container.get("game_id") or "")
            fallback_game_name = str(container.get("game_name") or "")
            if not fallback_game_name and fallback_game_id in game_by_id:
                fallback_game_name = game_by_id[fallback_game_id].get("game_name", "")

            for lead in as_list(container.get("pending_leads")):
                row = dict(lead) if isinstance(lead, dict) else {"lead": str(lead)}
                row.setdefault("game_id", fallback_game_id)
                row.setdefault("game_name", fallback_game_name)
                row.setdefault("source_ai", container.get("ai_tool") or "")
                row.setdefault("source_file", str(path))
                pending.append(row)

            for item in as_list(container.get("evidence") or container.get("items") or container.get("records")):
                if not isinstance(item, dict):
                    continue
                row = normalize_record(item, container, fallback_game_id, fallback_game_name)
                if not row["url"]:
                    pending.append(
                        {
                            "game_id": row["game_id"],
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
    return list(seen.values()), pending


def risk_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(value).lower(), 0)


def confidence_label(records: list[dict[str, Any]]) -> str:
    core = [item for item in records if item.get("evidence_level") == "core"]
    tools = {item.get("source_ai") for item in core if item.get("source_ai")}
    if len(core) >= 5 and len(tools) >= 3:
        return "中高"
    if len(core) >= 2:
        return "中"
    if len(core) == 1:
        return "低"
    return "不足"


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif; background:#f7f8fb; color:#172033; line-height:1.55; }}
    header {{ background:#16324f; color:white; padding:24px; }}
    main, .inner {{ max-width:1180px; margin:0 auto; }}
    main {{ padding:18px; }}
    section {{ background:white; border:1px solid #dde4ee; border-radius:8px; padding:16px; margin:14px 0; }}
    h1 {{ margin:0 0 6px; font-size:28px; }}
    h2 {{ margin:0 0 10px; font-size:20px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid #e3e8f0; padding:8px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; }}
    a {{ color:#075985; }}
    .muted {{ color:#667085; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
    .card {{ background:#f4f7fb; border:1px solid #dde4ee; border-radius:8px; padding:12px; }}
    .card b {{ display:block; font-size:24px; }}
    .risk {{ display:inline-block; min-width:54px; text-align:center; border-radius:999px; padding:2px 8px; font-weight:700; }}
    .risk.high {{ background:#fee4e2; color:#b42318; }}
    .risk.medium {{ background:#fff2d6; color:#b45309; }}
    .risk.low {{ background:#e7f6ec; color:#067647; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def render_game_page(game: dict[str, Any], records: list[dict[str, Any]], pending: list[dict[str, Any]], index_rel: str, report_date: str) -> str:
    records = sorted(records, key=lambda item: (-risk_rank(item.get("risk_level", "")), item.get("published_at", ""), item.get("platform", "")))
    platforms = Counter(item.get("platform") or "未知" for item in records)
    sentiments = Counter(item.get("player_tendency") or item.get("sentiment") or "未知" for item in records)
    ai_tools = Counter(item.get("source_ai") or "未知" for item in records)
    rows = "".join(
        f"<tr><td><span class='risk {esc(item.get('risk_level'))}'>{esc(item.get('risk_level'))}</span></td><td>{esc(item.get('source_ai'))}</td><td>{esc(item.get('platform'))}</td><td>{esc(item.get('published_at'))}</td><td><a href='{esc(item.get('url'))}' target='_blank' rel='noreferrer'>{esc(item.get('title'))}</a></td><td>{esc(item.get('player_tendency'))}</td><td>{esc(item.get('player_intent'))}</td><td>{esc(item.get('summary'))}</td><td>{esc(item.get('specific_player_opinions'))}</td></tr>"
        for item in records
    ) or "<tr><td colspan='9'>公开可检索样本不足，未形成可证据化结论。</td></tr>"
    pending_rows = "".join(f"<li>{esc(item.get('source_ai'))}: {esc(item.get('lead') or item.get('summary') or item)} <span class='muted'>{esc(item.get('reason'))}</span></li>" for item in pending) or "<li>暂无待验证线索。</li>"
    body = f"""
  <header><div class="inner">
    <h1>{esc(game.get('game_name'))}</h1>
    <p>报告日期：{esc(report_date)} | <a style="color:white" href="{esc(index_rel)}">返回总览</a></p>
  </div></header>
  <main>
    <section class="grid">
      <div class="card"><span>核心证据</span><b>{len(records)}</b></div>
      <div class="card"><span>覆盖平台</span><b>{len(platforms)}</b></div>
      <div class="card"><span>AI来源</span><b>{len(ai_tools)}</b></div>
      <div class="card"><span>可信度</span><b>{esc(confidence_label(records))}</b></div>
    </section>
    <section><h2>样本范围与限制</h2><p>本页只汇总带 URL 的公开可核查样本；AI 自行概括、无 URL、登录/验证码/403/付费墙限制内容仅进入待验证线索。公开可检索样本不代表全量社区舆情。</p></section>
    <section><h2>玩家倾向与平台分布</h2><p>玩家倾向：{esc('、'.join(f'{k}:{v}' for k, v in sentiments.most_common()) or '暂无')}</p><p>平台：{esc('、'.join(f'{k}:{v}' for k, v in platforms.most_common()) or '暂无')}</p><p>AI来源：{esc('、'.join(f'{k}:{v}' for k, v in ai_tools.most_common()) or '暂无')}</p></section>
    <section><h2>证据化事件</h2><table><thead><tr><th>风险</th><th>AI</th><th>平台</th><th>时间</th><th>证据链接</th><th>态度</th><th>意向</th><th>摘要</th><th>具体意见</th></tr></thead><tbody>{rows}</tbody></table></section>
    <section><h2>待验证线索</h2><ul>{pending_rows}</ul></section>
  </main>
"""
    return html_page(f"{game.get('game_name')} 舆情报告", body)


def render_index(games: list[dict[str, Any]], by_game: dict[str, list[dict[str, Any]]], pending_by_game: dict[str, list[dict[str, Any]]], report_date: str) -> str:
    all_records = [item for rows in by_game.values() for item in rows]
    platforms = Counter(item.get("platform") or "未知" for item in all_records)
    ai_tools = Counter(item.get("source_ai") or "未知" for item in all_records)
    high = [item for item in all_records if item.get("risk_level") == "high"]
    game_rows = ""
    for game in games:
        gid = game["game_id"]
        rows = by_game.get(gid, [])
        pending = pending_by_game.get(gid, [])
        sentiments = Counter(item.get("player_tendency") or item.get("sentiment") or "未知" for item in rows)
        link = f"games/{gid}_{slugify(game.get('game_name', gid))}.html"
        game_rows += f"<tr><td><a href='{esc(link)}'>{esc(game.get('game_name'))}</a></td><td>{len(rows)}</td><td>{len(pending)}</td><td>{esc(confidence_label(rows))}</td><td>{esc('、'.join(f'{k}:{v}' for k, v in sentiments.most_common()) or '暂无')}</td></tr>"
    high_rows = "".join(
        f"<li><strong>{esc(item.get('game_name'))}</strong> [{esc(item.get('platform'))}] <a href='{esc(item.get('url'))}' target='_blank'>{esc(item.get('title'))}</a>：{esc(item.get('summary'))}</li>"
        for item in sorted(high, key=lambda row: row.get("game_name", ""))[:30]
    ) or "<li>暂无高风险 URL-backed 样本。</li>"
    body = f"""
  <header><div class="inner">
    <h1>游戏名单舆情总览</h1>
    <p>报告日期：{esc(report_date)} | 样本：公开可检索网页与 Web AI 返回的 URL-backed 候选证据</p>
  </div></header>
  <main>
    <section class="grid">
      <div class="card"><span>监测游戏</span><b>{len(games)}</b></div>
      <div class="card"><span>核心证据</span><b>{len(all_records)}</b></div>
      <div class="card"><span>高风险事件</span><b>{len(high)}</b></div>
      <div class="card"><span>覆盖平台</span><b>{len(platforms)}</b></div>
    </section>
    <section><h2>样本范围与限制</h2><p>本报告只使用带 URL 的公开可核查样本。Web AI 结果只作为发现与交叉摘要；无 URL、无法验证、登录限制、验证码、403、付费墙或私密内容不进入核心结论。公开可检索样本不代表全量社区舆情。</p></section>
    <section><h2>值得关注的事件</h2><ul>{high_rows}</ul></section>
    <section><h2>平台与 AI 覆盖</h2><p>平台：{esc('、'.join(f'{k}:{v}' for k, v in platforms.most_common()) or '暂无')}</p><p>AI来源：{esc('、'.join(f'{k}:{v}' for k, v in ai_tools.most_common()) or '暂无')}</p></section>
    <section><h2>按游戏分组</h2><table><thead><tr><th>游戏</th><th>核心证据</th><th>待验证</th><th>可信度</th><th>玩家倾向</th></tr></thead><tbody>{game_rows}</tbody></table></section>
  </main>
"""
    return html_page("游戏名单舆情总览", body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list_json", help="Path to game_list.json")
    parser.add_argument("inputs", nargs="*", help="AI output JSON files or directories")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--report-date", default=date.today().isoformat())
    args = parser.parse_args()

    data = load_json(Path(args.game_list_json))
    games = data if isinstance(data, list) else data.get("games", [])
    evidence, pending = load_outputs(collect_json_files(args.inputs), games) if args.inputs else ([], [])

    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pending_by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        by_game[item.get("game_id") or ""].append(item)
    for item in pending:
        pending_by_game[item.get("game_id") or ""].append(item)

    out_dir = Path(args.output_dir)
    games_dir = out_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    for game in games:
        gid = game["game_id"]
        page = render_game_page(game, by_game.get(gid, []), pending_by_game.get(gid, []), "../index.html", args.report_date)
        (games_dir / f"{gid}_{slugify(game.get('game_name', gid))}.html").write_text(page, encoding="utf-8")
    (out_dir / "index.html").write_text(render_index(games, by_game, pending_by_game, args.report_date), encoding="utf-8")
    (out_dir / "normalized_evidence.json").write_text(json.dumps({"evidence": evidence, "pending_leads": pending}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "index": str(out_dir / "index.html"),
                "game_reports": len(games),
                "evidence": len(evidence),
                "pending_leads": len(pending),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
