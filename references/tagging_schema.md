# Tagging Schema

Tag each evidence item with a structured record.

```json
{
  "evidence_id": "ev_001",
  "sentiment": "positive | negative | neutral | mixed",
  "topic": "剧情 | 角色 | 玩法 | 氪金 | 优化 | 活动 | 版本 | BUG | 回坑 | 竞品比较 | 其他",
  "player_intent": "抱怨 | 建议 | 观望 | 推荐 | 退坑 | 回流 | 攻略 | 争议讨论",
  "risk_level": "low | medium | high",
  "actionable": true,
  "summary": "一句话概括玩家观点",
  "evidence_quote_or_snippet": "可验证摘录或搜索片段",
  "confidence": 0.72
}
```

## Tagging Guidelines

- Use `mixed` sentiment when the same evidence contains praise and criticism.
- Use `risk_level=high` for concentrated anger, refund/退坑 calls, organized boycotts, severe technical failures, or controversy likely to spread.
- Use `actionable=true` only when the evidence implies a product, community, operation, narrative, monetization, technical, or design action.
- Prefer the visible snippet over invented quotes. Do not fabricate direct quotes.
- Lower confidence for search snippets, inaccessible pages, or Web AI summaries.
