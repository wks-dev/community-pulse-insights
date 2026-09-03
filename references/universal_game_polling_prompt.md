# Universal Game Polling Prompt

Use this reference when building a reusable prompt for game-list polling. Keep `{game_name}` blank in the template until a script or operator fills it for a specific game.

## Placeholders

- `{game_id}`: stable ID from the game list, such as `game_001`.
- `{game_name}`: display name from the game list.
- `{aliases}`: aliases joined by ` / `.
- `{aliases_json}`: aliases as a JSON array.
- `{ai_tool}`: one of `元宝`, `豆包`, `文心一言`, `千问`, `点点`, `知乎直答`, `Gemini`, `Grok`.
- `{platform_focus}`: the platform coverage expected from that AI.
- `{tool_identity_guard}`: a guardrail that prevents the AI tool name from becoming a search target.
- `{start_date}` and `{end_date}`: absolute dates.
- `{max_items}`: maximum evidence items, usually 3.

## Template

```text
请检索《{game_name}》最近7天内的公开信息，测试时间截止到 {end_date}。

游戏ID：{game_id}
游戏别名：{aliases}
当前AI工具：{ai_tool}
重点平台范围：{platform_focus}
{tool_identity_guard}

请最多返回 {max_items} 条重要内容，内容需要包含：
1. 游戏相关事件；
2. 当前玩家舆情；
3. 玩家意向，例如入坑、回流、退坑、抽卡、付费或观望；
4. 玩家对剧情、角色、玩法、优化、付费或运营的具体意见。

每条内容必须提供：
- 事件或讨论标题；
- 简要说明；
- 玩家主要态度；
- 信息发布时间；
- 来源平台；
- 可以核查的帖子、新闻、公告或视频链接；
- 该结论由哪条证据支持。

要求：
- 不得编造链接、帖子、新闻、标题、发布时间或玩家观点；
- 找不到可靠证据时明确说明；
- 没有 URL 的内容不得进入 evidence，只能进入 pending_leads；
- 遇到登录、403、验证码、付费墙、私密群或需要绕过访问控制的页面，不得绕过，只能说明样本限制；
- 最多输出 {max_items} 条，不要长篇介绍。

请严格输出 JSON，不要输出 Markdown：
{
  "ai_tool": "{ai_tool}",
  "game_id": "{game_id}",
  "game_name": "{game_name}",
  "aliases": {aliases_json},
  "time_range": "{start_date} 至 {end_date}",
  "platform_focus": "{platform_focus}",
  "evidence": [
    {
      "title": "",
      "event_or_discussion": "",
      "summary": "",
      "player_sentiment": "positive / negative / neutral / mixed",
      "player_intent": "入坑 / 回流 / 退坑 / 抽卡 / 付费 / 观望 / 攻略 / 争议讨论 / 其他",
      "specific_player_opinions": "",
      "published_at": "",
      "source_platform": "",
      "url": "",
      "evidence_support": "",
      "risk_level": "low / medium / high",
      "access_status": "accessible / search_snippet_only / blocked_login / forbidden_403 / captcha / paywalled / no_url / unknown",
      "limitations": ""
    }
  ],
  "pending_leads": [
    {
      "lead": "",
      "reason": "无URL、无法验证、登录限制、AI只给概括等"
    }
  ]
}
```

## AI Platform Focus

- 元宝：微信生态、公众号、新闻、腾讯系内容、中文网页。
- 豆包：抖音、微博、B站、中文网页、新闻和 TikTok 线索。
- 文心一言：百度、中文网页、新闻、贴吧、百度知道/百科生态。
- 千问：中文网页、新闻、公开搜索、社区线索；千问只是提交问题的 AI 工具，不是检索对象。
- 点点：小红书、种草内容、社媒讨论。小红书证据优先 `xiaohongshu.com` 或 `xhslink.com`。
- 知乎直答：知乎问答、争议复盘、中文网页。
- Gemini：全球公开网页、YouTube、Instagram。
- Grok：X/Twitter、全球社媒和实时公开讨论。
