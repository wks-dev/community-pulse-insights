# Evidence Schema

Represent evidence pool records as JSON objects.

```json
{
  "evidence_id": "ev_001",
  "platform": "NGA",
  "game_name": "原神",
  "source_type": "original_post | comment | official | search_result | web_ai_summary | user_supplied_url | secondary_summary",
  "title": "帖子标题",
  "url": "https://example.com/post",
  "published_at": "2026-07-20",
  "retrieved_at": "2026-07-23",
  "snippet": "搜索片段或可见评论摘录",
  "summary": "证据内容摘要",
  "access_status": "accessible | search_snippet_only | blocked_login | forbidden_403 | captcha | paywalled | no_url | unknown",
  "evidence_level": "core | supporting | secondary_only | excluded",
  "confidence": 0.75,
  "limitations": "公开可检索样本，不代表全量社区舆情"
}
```

## Evidence Levels

- `core`: Accessible original posts/comments, official pages, or directly verifiable source pages with URLs.
- `supporting`: Search-result pages, snippets, accessible repost indexes, or public pages that summarize linked source material.
- `secondary_only`: Web AI summaries or other summaries without verified source access. URL-less records must stay here.
- `excluded`: Private, inaccessible, unverifiable, duplicate, or access-control-bypassed material.

## Required Rules

- Deduplicate by normalized URL.
- Do not upgrade URL-less records beyond `secondary_only`.
- Mark login, 403, CAPTCHA, paywall, or private-group sources as limited or excluded.
- Keep retrieval date for every record.
- Preserve limitations in downstream reports.
