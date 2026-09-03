#!/usr/bin/env python3
"""Render a per-game daily HTML intelligence report."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from datetime import date
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def load_json(path: str) -> Any:
    return json.load(open(path, encoding="utf-8"))


def load_games(path: str) -> list[dict[str, Any]]:
    data = load_json(path)
    return data if isinstance(data, list) else data.get("games", [])


def load_evidence(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = load_json(path)
    if isinstance(data, list):
        return data, []
    return data.get("evidence", []), data.get("pending_leads", [])


def risk_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(value).lower(), 0)


def tendency(records: list[dict[str, Any]]) -> str:
    counts = Counter(item.get("player_tendency") or item.get("sentiment") or "unknown" for item in records)
    return counts.most_common(1)[0][0] if counts else "无公开样本"


def render(game_list: list[dict[str, Any]], evidence: list[dict[str, Any]], pending: list[dict[str, Any]], title: str) -> str:
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        by_game[item.get("game_id") or item.get("game_name") or "unknown"].append(item)

    high_risk = sorted([item for item in evidence if item.get("risk_level") == "high"], key=lambda x: x.get("game_name", ""))
    platforms = Counter(item.get("platform") or "unknown" for item in evidence)
    ai_tools = Counter(item.get("source_ai") or "search" for item in evidence)

    sections = []
    for game in game_list:
        game_id = game.get("game_id")
        rows = sorted(by_game.get(game_id, []), key=lambda item: (-risk_rank(item.get("risk_level", "")), item.get("platform", "")))
        aliases = " / ".join(game.get("aliases") or [game.get("game_name")])
        if rows:
            event_rows = "".join(
                f"<tr><td><span class='risk {esc(item.get('risk_level'))}'>{esc(item.get('risk_level'))}</span></td><td>{esc(item.get('platform'))}</td><td>{esc(item.get('event_type'))}</td><td><a href='{esc(item.get('url'))}' target='_blank' rel='noreferrer'>{esc(item.get('title') or item.get('summary'))}</a></td><td>{esc(item.get('player_tendency'))}</td><td>{esc(item.get('summary'))}</td><td>{esc(item.get('why_watch'))}</td></tr>"
                for item in rows
                if item.get("url")
            )
        else:
            event_rows = "<tr><td colspan='7'>今日公开可检索样本不足，未形成可证据化结论。</td></tr>"
        sections.append(
            f"""
            <section>
              <h2>{esc(game.get('game_name'))}</h2>
              <p class="muted">Aliases: {esc(aliases)}</p>
              <p>玩家倾向：<strong>{esc(tendency(rows))}</strong> | 证据数：{len(rows)}</p>
              <table>
                <thead><tr><th>风险</th><th>平台</th><th>事件类型</th><th>证据</th><th>玩家倾向</th><th>摘要</th><th>关注理由</th></tr></thead>
                <tbody>{event_rows}</tbody>
              </table>
            </section>
            """
        )

    evidence_rows = "".join(
        f"<tr><td>{esc(item.get('evidence_id'))}</td><td>{esc(item.get('game_name'))}</td><td>{esc(item.get('platform'))}</td><td>{esc(item.get('source_ai'))}</td><td><a href='{esc(item.get('url'))}' target='_blank' rel='noreferrer'>{esc(item.get('title') or item.get('url'))}</a></td><td>{esc(item.get('evidence_level'))}</td><td>{esc(item.get('limitations'))}</td></tr>"
        for item in evidence
        if item.get("url")
    )
    pending_rows = "".join(f"<li>{esc(item.get('game_id'))}: {esc(item.get('lead') or item.get('summary') or item)}</li>" for item in pending) or "<li>暂无 URL-less 待验证线索。</li>"
    risk_rows = "".join(
        f"<li><strong>{esc(item.get('game_name'))}</strong> [{esc(item.get('platform'))}] {esc(item.get('summary'))} <a href='{esc(item.get('url'))}' target='_blank'>证据</a></li>"
        for item in high_risk[:20]
    ) or "<li>暂无高风险证据化事件。</li>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; background:#f6f8fb; color:#172033; line-height:1.6; }}
    header {{ background:#102a43; color:white; padding:30px 24px; }}
    main, .inner {{ max-width:1180px; margin:0 auto; }}
    main {{ padding:20px; }}
    section {{ background:white; border:1px solid #d9e1ec; border-radius:8px; padding:18px; margin:16px 0; }}
    h1 {{ margin:0 0 8px; font-size:30px; }}
    h2 {{ margin:0 0 10px; font-size:21px; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:16px; }}
    .card {{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.25); border-radius:8px; padding:12px; }}
    .card b {{ display:block; font-size:24px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid #d9e1ec; padding:9px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; }}
    a {{ color:#075985; }}
    .muted {{ color:#667085; }}
    .risk {{ display:inline-block; min-width:58px; text-align:center; border-radius:999px; padding:2px 8px; font-weight:700; }}
    .risk.high {{ background:#fee4e2; color:#b42318; }}
    .risk.medium {{ background:#fff2d6; color:#b45309; }}
    .risk.low {{ background:#e7f6ec; color:#067647; }}
  </style>
</head>
<body>
  <header><div class="inner">
    <h1>{esc(title)}</h1>
    <p>报告日期：{date.today().isoformat()} | 样本边界：公开可检索样本，不代表全平台全量舆情。</p>
    <div class="cards">
      <div class="card"><span>监控游戏</span><b>{len(game_list)}</b></div>
      <div class="card"><span>证据记录</span><b>{len(evidence)}</b></div>
      <div class="card"><span>高风险事件</span><b>{len(high_risk)}</b></div>
      <div class="card"><span>覆盖平台</span><b>{len(platforms)}</b></div>
    </div>
  </div></header>
  <main>
    <section><h2>1. 日报总览</h2><p>本报告按游戏分组呈现今日公开可检索舆情、值得关注事件、玩家倾向与风险。</p></section>
    <section><h2>2. 样本范围与限制</h2><p>仅使用公开可访问页面、搜索可验证页面和 Web AI 返回的 URL-backed 候选证据。登录、验证码、403、付费墙、私密群和无 URL 内容不进入核心结论。</p></section>
    <section><h2>3. 值得关注的事件</h2><ul>{risk_rows}</ul></section>
    <section><h2>4. 平台差异</h2><p>平台分布：{esc('、'.join(f'{k}:{v}' for k, v in platforms.most_common()))}</p><p>AI/搜索来源：{esc('、'.join(f'{k}:{v}' for k, v in ai_tools.most_common()))}</p></section>
    {''.join(sections)}
    <section><h2>9. 证据链接表</h2><table><thead><tr><th>ID</th><th>游戏</th><th>平台</th><th>来源AI</th><th>链接</th><th>等级</th><th>限制</th></tr></thead><tbody>{evidence_rows}</tbody></table></section>
    <section><h2>10. 待验证线索</h2><ul>{pending_rows}</ul></section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_list_json")
    parser.add_argument("daily_evidence_json")
    parser.add_argument("--title", default="游戏舆情日报")
    parser.add_argument("--output", "-o", default="daily_game_report.html")
    args = parser.parse_args()

    report = render(load_games(args.game_list_json), *load_evidence(args.daily_evidence_json), title=args.title)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(json.dumps({"output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
