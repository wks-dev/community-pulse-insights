# Daily Monitoring Workflow

Use this reference for scheduled daily game-list monitoring.

## Inputs

- `game_list.xlsx`, `.xls`, `.csv`, or `.tsv`
- Optional platform list. Default: all supported public platforms.
- Optional Web AI tools. Default: route by matrix.
- Optional lookback window. Default: 24 hours for traditional daily jobs; 7 days for first baseline run. Use `fast_daily_intelligence_workflow.md` for the separate 3-day company/market daily mode.

## Game List Rules

The game list may have no headers. If no header is detected, treat every non-empty cell in a row as an alias for the same game.

If headers exist, recognize these names:

- game, game_name, 游戏, 游戏名, 中文名, 名称
- english_name, en, 英文名
- alias, aliases, 别名
- platform, platforms, 平台
- enabled, 启用
- priority, 优先级
- notes, 备注

Use the first non-empty alias as display name, but keep all aliases in prompts.

## Daily Evidence Fields

Each AI/search output record should contain:

```json
{
  "game_id": "game_001",
  "game_name": "Display Name",
  "aliases": ["Alias A", "Alias B"],
  "platform": "Xiaohongshu",
  "source_ai": "点点",
  "title": "Post title",
  "url": "https://example.com/post",
  "published_at": "2026-07-23",
  "retrieved_at": "2026-07-23",
  "event_type": "版本更新 | 争议 | BUG | 优化 | 福利 | 活动 | 角色 | 剧情 | 竞品比较 | 其他",
  "player_tendency": "正面 | 负面 | 中立 | 分化 | 观望",
  "sentiment": "positive | negative | neutral | mixed",
  "risk_level": "low | medium | high",
  "snippet": "Visible snippet or accessible excerpt",
  "summary": "Evidence-backed summary",
  "why_watch": "Why this item deserves attention",
  "access_status": "accessible | search_snippet_only | blocked_login | forbidden_403 | captcha | paywalled | no_url | unknown",
  "evidence_level": "core | supporting | secondary_only | excluded",
  "limitations": "Sample or access limits"
}
```

## Output Rules

- Group report sections by game.
- Each event under a game must include an evidence URL or be moved to `待验证线索`.
- Highlight high-risk and newly rising events at the top.
- Do not state full-platform coverage unless a true platform data export/API backs it.
