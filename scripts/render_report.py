#!/usr/bin/env python3
"""Render a Markdown or standalone HTML game-community sentiment report."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def as_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("tags", "tagged_evidence", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def evidence_map(pool: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("evidence_id", ""): item for item in pool}


def confidence_label(pool: list[dict[str, Any]]) -> str:
    core = sum(1 for item in pool if item.get("evidence_level") == "core")
    supporting = sum(1 for item in pool if item.get("evidence_level") == "supporting")
    if core >= 5:
        return "high"
    if core >= 2 or supporting >= 5:
        return "medium"
    return "low"


def grouped_context(pool: list[dict[str, Any]], tags: list[dict[str, Any]]) -> dict[str, Any]:
    ev_by_id = evidence_map(pool)
    levels = Counter(item.get("evidence_level", "unknown") for item in pool)
    topic_counts = Counter(tag.get("topic", "其他") for tag in tags)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        grouped[tag.get("topic", "其他")].append(tag)
    return {
        "ev_by_id": ev_by_id,
        "levels": levels,
        "topic_counts": topic_counts,
        "grouped": grouped,
        "risk_tags": [tag for tag in tags if tag.get("risk_level") in {"medium", "high"}],
        "secondary": [item for item in pool if item.get("evidence_level") == "secondary_only"],
        "platforms": sorted({item.get("platform", "unknown") for item in pool if item.get("platform")}),
        "games": sorted({item.get("game_name", "unknown") for item in pool if item.get("game_name")}),
    }


def bullet_tags(tags: list[dict[str, Any]], sentiment: str) -> list[str]:
    lines = []
    for tag in tags:
        if tag.get("sentiment") == sentiment:
            evidence_id = tag.get("evidence_id", "")
            lines.append(f"- {tag.get('summary', '未提供摘要')} [{evidence_id}]")
    return lines or ["- 样本不足，未形成稳定结论。"]


def render_markdown(pool: list[dict[str, Any]], tags: list[dict[str, Any]], title: str) -> str:
    ctx = grouped_context(pool, tags)
    levels = ctx["levels"]
    topic_counts = ctx["topic_counts"]
    grouped = ctx["grouped"]
    platforms = ctx["platforms"]
    games = ctx["games"]
    risk_tags = ctx["risk_tags"]
    secondary = ctx["secondary"]
    ev_by_id = ctx["ev_by_id"]

    lines = [f"# {title}", ""]
    lines.extend(
        [
            "## 1. 总体结论",
            "",
            f"- 本报告基于 {len(pool)} 条候选证据，其中 core={levels.get('core', 0)}、supporting={levels.get('supporting', 0)}、secondary_only={levels.get('secondary_only', 0)}。",
            f"- 高频主题集中在：{', '.join(topic for topic, _ in topic_counts.most_common(5)) or '样本不足'}。",
            f"- 当前可信度为 {confidence_label(pool)}，结论仅代表公开可检索样本。",
            "",
            "## 2. 样本范围与限制",
            "",
            f"- 分析目标：{title}",
            f"- 平台：{', '.join(platforms) or '未标注'}",
            f"- 游戏：{', '.join(games) or '未标注'}",
            f"- 检索日期：{date.today().isoformat()}",
            f"- 样本数量：{len(pool)}",
            "- 样本边界：公开可检索样本，不代表全量社区舆情。",
            f"- 可信度：{confidence_label(pool)}",
            "- 证据限制：登录、403、验证码、付费墙、私密群或无 URL 内容不得进入核心结论。",
            "",
            "## 3. 高频主题",
            "",
            "| 主题 | 数量 | 代表观点 | 证据 |",
            "|---|---:|---|---|",
        ]
    )
    for topic, count in topic_counts.most_common():
        example = grouped[topic][0]
        lines.append(f"| {topic} | {count} | {example.get('summary', '')} | [{example.get('evidence_id', '')}] |")
    if not topic_counts:
        lines.append("| 样本不足 | 0 | 尚未打标 | - |")

    lines.extend(["", "## 4. 正面玩家意见", ""])
    lines.extend(bullet_tags(tags, "positive"))
    lines.extend(["", "## 5. 负面玩家意见", ""])
    lines.extend(bullet_tags(tags, "negative"))
    lines.extend(["", "## 6. 主要争议点", ""])
    mixed = [tag for tag in tags if tag.get("sentiment") == "mixed" or tag.get("player_intent") == "争议讨论"]
    lines.extend([f"- {tag.get('summary', '未提供摘要')} [{tag.get('evidence_id', '')}]" for tag in mixed] or ["- 样本不足，未形成稳定争议点。"])
    lines.extend(["", "## 7. 玩家建议", ""])
    suggestions = [tag for tag in tags if tag.get("player_intent") == "建议" or tag.get("actionable") is True]
    lines.extend([f"- {tag.get('summary', '未提供摘要')} [{tag.get('evidence_id', '')}]" for tag in suggestions] or ["- 暂无足够证据支持具体建议。"])
    lines.extend(["", "## 8. 风险预警", "", "| 风险 | 等级 | 触发信号 | 建议动作 | 证据 |", "|---|---|---|---|---|"])
    for tag in risk_tags:
        lines.append(f"| {tag.get('topic', '其他')} | {tag.get('risk_level', 'low')} | {tag.get('summary', '')} | 进一步核验样本并跟踪扩散 | [{tag.get('evidence_id', '')}] |")
    if not risk_tags:
        lines.append("| 暂未发现稳定高风险信号 | low | 样本不足或风险分散 | 继续观察 | - |")
    lines.extend(["", "## 9. 可借鉴设计点", ""])
    actionable = [tag for tag in tags if tag.get("actionable") is True]
    lines.extend([f"- {tag.get('summary', '未提供摘要')} [{tag.get('evidence_id', '')}]" for tag in actionable] or ["- 暂无足够证据提炼可借鉴设计点。"])
    lines.extend(["", "## 10. 平台差异与舆情发展", ""])
    lines.append("- 若样本覆盖多个平台，请按平台列出情绪差异、议题差异、传播先后和趋势判断。")
    lines.extend(["", "## 11. 证据链接表", "", "| ID | 平台 | 标题 | 链接 | 时间 | 证据等级 | 限制 |", "|---|---|---|---|---|---|---|"])
    for item in pool:
        title_text = item.get("title") or item.get("summary") or "未命名证据"
        url = item.get("url") or ""
        link = f"[{title_text}]({url})" if url else title_text
        lines.append(f"| {item.get('evidence_id', '')} | {item.get('platform', '')} | {link} | {url or '-'} | {item.get('published_at', '')} | {item.get('evidence_level', '')} | {item.get('limitations', '')} |")
    lines.extend(["", "## 12. 待验证线索", ""])
    if secondary:
        for item in secondary:
            lines.append(f"- {item.get('summary') or item.get('snippet') or item.get('title') or '无摘要'} [{item.get('evidence_id')}]")
    else:
        lines.append("- 暂无 URL-less 或仅 Web AI 概括线索。")

    missing_tag_ids = sorted(set(ev_by_id) - {tag.get("evidence_id") for tag in tags})
    if missing_tag_ids:
        lines.extend(["", f"> 未打标证据：{', '.join(missing_tag_ids)}"])
    return "\n".join(lines) + "\n"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_html(pool: list[dict[str, Any]], tags: list[dict[str, Any]], title: str) -> str:
    ctx = grouped_context(pool, tags)
    levels = ctx["levels"]
    topic_counts = ctx["topic_counts"]
    grouped = ctx["grouped"]
    platforms = ctx["platforms"]
    games = ctx["games"]
    risk_tags = ctx["risk_tags"]
    secondary = ctx["secondary"]
    confidence = confidence_label(pool)

    def tag_items(sentiment: str) -> str:
        items = [tag for tag in tags if tag.get("sentiment") == sentiment]
        if not items:
            return "<li>样本不足，未形成稳定结论。</li>"
        return "\n".join(f"<li>{esc(tag.get('summary', '未提供摘要'))} <span class=\"ev\">[{esc(tag.get('evidence_id'))}]</span></li>" for tag in items)

    theme_rows = []
    for topic, count in topic_counts.most_common():
        example = grouped[topic][0]
        theme_rows.append(f"<tr><td>{esc(topic)}</td><td>{count}</td><td>{esc(example.get('summary'))}</td><td>{esc(example.get('evidence_id'))}</td></tr>")
    if not theme_rows:
        theme_rows.append("<tr><td>样本不足</td><td>0</td><td>尚未打标</td><td>-</td></tr>")

    risk_rows = []
    for tag in risk_tags:
        risk_rows.append(
            f"<tr><td>{esc(tag.get('topic', '其他'))}</td><td><span class=\"risk {esc(tag.get('risk_level', 'low'))}\">{esc(tag.get('risk_level', 'low'))}</span></td><td>{esc(tag.get('summary'))}</td><td>进一步核验样本并跟踪扩散</td><td>{esc(tag.get('evidence_id'))}</td></tr>"
        )
    if not risk_rows:
        risk_rows.append("<tr><td>暂未发现稳定高风险信号</td><td><span class=\"risk low\">low</span></td><td>样本不足或风险分散</td><td>继续观察</td><td>-</td></tr>")

    actionable = [tag for tag in tags if tag.get("actionable") is True]
    actionable_html = "\n".join(f"<li>{esc(tag.get('summary', '未提供摘要'))} <span class=\"ev\">[{esc(tag.get('evidence_id'))}]</span></li>" for tag in actionable) or "<li>暂无足够证据提炼可借鉴设计点。</li>"

    mixed = [tag for tag in tags if tag.get("sentiment") == "mixed" or tag.get("player_intent") == "争议讨论"]
    mixed_html = "\n".join(f"<li>{esc(tag.get('summary', '未提供摘要'))} <span class=\"ev\">[{esc(tag.get('evidence_id'))}]</span></li>" for tag in mixed) or "<li>样本不足，未形成稳定争议点。</li>"

    suggestions = [tag for tag in tags if tag.get("player_intent") == "建议" or tag.get("actionable") is True]
    suggestion_html = "\n".join(f"<li>{esc(tag.get('summary', '未提供摘要'))} <span class=\"ev\">[{esc(tag.get('evidence_id'))}]</span></li>" for tag in suggestions) or "<li>暂无足够证据支持具体建议。</li>"

    evidence_rows = []
    for item in pool:
        url = item.get("url") or ""
        title_text = item.get("title") or item.get("summary") or "未命名证据"
        title_cell = f"<a href=\"{esc(url)}\" target=\"_blank\" rel=\"noreferrer\">{esc(title_text)}</a>" if url else esc(title_text)
        evidence_rows.append(
            f"<tr><td>{esc(item.get('evidence_id'))}</td><td>{esc(item.get('platform'))}</td><td>{title_cell}</td><td class=\"url\">{esc(url or '-')}</td><td>{esc(item.get('published_at'))}</td><td>{esc(item.get('evidence_level'))}</td><td>{esc(item.get('limitations'))}</td></tr>"
        )

    pending_html = "\n".join(f"<li>{esc(item.get('summary') or item.get('snippet') or item.get('title') or '无摘要')} <span class=\"ev\">[{esc(item.get('evidence_id'))}]</span></li>" for item in secondary) or "<li>暂无 URL-less 或仅 Web AI 概括线索。</li>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#667085; --line:#d9e1ec; --bg:#f6f8fb; --panel:#ffffff; --accent:#0f766e; --warn:#b45309; --bad:#b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; color:var(--ink); background:var(--bg); line-height:1.65; }}
    header {{ background:linear-gradient(135deg, #102a43, #0f766e); color:white; padding:36px 28px; }}
    header .inner, main {{ max-width:1120px; margin:0 auto; }}
    h1 {{ margin:0 0 10px; font-size:30px; letter-spacing:0; }}
    h2 {{ margin:0 0 14px; font-size:20px; letter-spacing:0; }}
    p {{ margin:0 0 10px; }}
    main {{ padding:24px 20px 48px; }}
    section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin:16px 0; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-top:16px; }}
    .card {{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.28); border-radius:8px; padding:14px; }}
    .card b {{ display:block; font-size:24px; }}
    .muted {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; color:#344054; font-weight:600; }}
    ul {{ margin:0; padding-left:20px; }}
    a {{ color:#075985; }}
    .ev {{ color:var(--accent); font-weight:600; }}
    .risk {{ display:inline-block; min-width:56px; text-align:center; border-radius:999px; padding:2px 8px; font-weight:600; }}
    .risk.low {{ background:#e7f6ec; color:#067647; }}
    .risk.medium {{ background:#fff2d6; color:var(--warn); }}
    .risk.high {{ background:#fee4e2; color:var(--bad); }}
    .url {{ word-break:break-all; color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }}
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>{esc(title)}</h1>
      <p>样本边界：公开可检索样本，不代表全量社区舆情。检索日期：{date.today().isoformat()}</p>
      <div class="cards">
        <div class="card"><span>候选证据</span><b>{len(pool)}</b></div>
        <div class="card"><span>Core / Supporting</span><b>{levels.get('core', 0)} / {levels.get('supporting', 0)}</b></div>
        <div class="card"><span>可信度</span><b>{confidence}</b></div>
        <div class="card"><span>平台</span><b>{esc(', '.join(platforms) or '未标注')}</b></div>
      </div>
    </div>
  </header>
  <main>
    <section><h2>1. 总体结论</h2><ul><li>本报告基于 {len(pool)} 条候选证据，其中 core={levels.get('core', 0)}、supporting={levels.get('supporting', 0)}、secondary_only={levels.get('secondary_only', 0)}。</li><li>高频主题集中在：{esc(', '.join(topic for topic, _ in topic_counts.most_common(5)) or '样本不足')}。</li><li>当前可信度为 {confidence}，结论仅代表公开可检索样本。</li></ul></section>
    <section><h2>2. 样本范围与限制</h2><p>分析目标：{esc(title)}</p><p>平台：{esc(', '.join(platforms) or '未标注')}</p><p>游戏：{esc(', '.join(games) or '未标注')}</p><p>证据限制：登录、403、验证码、付费墙、私密群或无 URL 内容不得进入核心结论。</p></section>
    <section><h2>3. 高频主题</h2><table><thead><tr><th>主题</th><th>数量</th><th>代表观点</th><th>证据</th></tr></thead><tbody>{''.join(theme_rows)}</tbody></table></section>
    <div class="grid"><section><h2>4. 正面玩家意见</h2><ul>{tag_items('positive')}</ul></section><section><h2>5. 负面玩家意见</h2><ul>{tag_items('negative')}</ul></section></div>
    <section><h2>6. 主要争议点</h2><ul>{mixed_html}</ul></section>
    <section><h2>7. 玩家建议</h2><ul>{suggestion_html}</ul></section>
    <section><h2>8. 风险预警</h2><table><thead><tr><th>风险</th><th>等级</th><th>触发信号</th><th>建议动作</th><th>证据</th></tr></thead><tbody>{''.join(risk_rows)}</tbody></table></section>
    <section><h2>9. 可借鉴设计点</h2><ul>{actionable_html}</ul></section>
    <section><h2>10. 平台差异与舆情发展</h2><p class="muted">若样本覆盖多个平台，请按平台列出情绪差异、议题差异、传播先后和趋势判断。</p></section>
    <section><h2>11. 证据链接表</h2><table><thead><tr><th>ID</th><th>平台</th><th>标题</th><th>链接</th><th>时间</th><th>等级</th><th>限制</th></tr></thead><tbody>{''.join(evidence_rows)}</tbody></table></section>
    <section><h2>12. 待验证线索</h2><ul>{pending_html}</ul></section>
  </main>
</body>
</html>
"""


def infer_format(output: str, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    return "html" if Path(output).suffix.lower() in {".html", ".htm"} else "markdown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_pool", help="Path to evidence_pool.json")
    parser.add_argument("tagged_evidence", nargs="?", default="tagged_evidence.json")
    parser.add_argument("--title", default="游戏社区舆情报告")
    parser.add_argument("--output", "-o", default="sentiment_report.html")
    parser.add_argument("--format", choices=["auto", "markdown", "html"], default="auto")
    args = parser.parse_args()

    pool = as_list(load_json(args.evidence_pool, []))
    tags = as_list(load_json(args.tagged_evidence, []))
    output_format = infer_format(args.output, args.format)
    report = render_html(pool, tags, args.title) if output_format == "html" else render_markdown(pool, tags, args.title)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(json.dumps({"output": args.output, "format": output_format, "evidence": len(pool), "tags": len(tags)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
