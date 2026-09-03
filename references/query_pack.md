# Query Pack Generation

Generate search queries from:

- platform: NGA, TapTap, Steam, Bilibili, Weibo, Xiaohongshu, Tieba, Reddit, all-platform public web, or broad web
- game_name: one or more games, if known
- category_terms: genre/type/segment terms when no specific game is known
- time_range: explicit date range or recent window
- analysis_goals: opinion, controversy, risk, negative review, version feedback, comparison, design lessons, trend development
- topic keywords: 剧情, 角色, 玩法, 氪金, 优化, 活动, 版本, BUG, 回坑, 退坑, 竞品

Prefer public indexed URLs. Do not include instructions to bypass login or access controls.

## Target Strategy

- If a game is known, anchor queries on the game name.
- If only a category/type is known, anchor queries on category terms and add discovery terms such as "代表游戏", "玩家讨论", "口碑", "争议", "近期".
- If all-platform analysis is requested, generate queries for each supported platform and add cross-platform trend queries.
- If a platform is Xiaohongshu, expect some content to be search-snippet-only. Keep URL-less or inaccessible claims out of core conclusions.

## Platform Query Patterns

### NGA

- `site:ngabbs.com/read.php {target} 玩家意见`
- `site:ngabbs.com/read.php {target} 剧情 吐槽`
- `site:ngabbs.com/read.php {target} 回坑 入坑`
- `site:ngabbs.com/read.php {target} 版本 争议`
- `NGA {target} 玩家 舆情`

### TapTap

- `site:taptap.cn {target} 评价`
- `site:taptap.cn {target} 新版本 反馈`
- `site:taptap.cn {target} 差评`
- `TapTap {target} 玩家 口碑`
- `TapTap {target} 优化 BUG 氪金`

### Steam

- `site:steamcommunity.com/app {target} review negative`
- `site:store.steampowered.com/app {target} reviews`
- `Steam {target} 差评 原因`
- `Steam {target} recent reviews negative`
- `Steam {target} optimization bug monetization`

### Bilibili

- `site:bilibili.com/video {target} 新版本 评价`
- `site:bilibili.com/read {target} 玩家 反馈`
- `B站 {target} 吐槽`
- `Bilibili {target} 争议 版本`
- `{target} 评论区 玩家 反馈 B站`

### Weibo

- `site:weibo.com {target} 玩家 反馈`
- `微博 {target} 新版本 争议`
- `微博 {target} 超话 吐槽`
- `{target} 微博 氪金 优化 BUG`

### Xiaohongshu

- `site:xiaohongshu.com {target} 游戏 体验`
- `site:xiaohongshu.com {target} 新版本`
- `小红书 {target} 新手 入坑`
- `小红书 {target} 吐槽`
- `{target} 小红书 剧情 角色 玩法`
- `{target} 小红书 避雷 推荐`

### Tieba

- `site:tieba.baidu.com/p {target} 玩家 反馈`
- `{target} 吧 新版本 吐槽`
- `{target} 吧 退坑 回坑`
- `{target} 贴吧 争议`

### Reddit

- `site:reddit.com/r/ {target} discussion`
- `site:reddit.com/r/ {target} update feedback`
- `Reddit {target} controversy`
- `Reddit {target} review negative`
- `{target} subreddit player feedback`

## Category-Only Examples

For "最近二游玩家舆情":

- `二游 玩家 舆情 最近`
- `二游 新版本 争议 玩家反馈`
- `二次元手游 TapTap 差评 原因`
- `小红书 二游 入坑 避雷`
- `B站 二游 节奏 版本`
- `NGA 二游 玩家 争议`

For "开放世界手游口碑变化":

- `开放世界手游 玩家 口碑 近期`
- `开放世界手游 吐槽 优化 内容消耗`
- `TapTap 开放世界手游 评价`
- `B站 开放世界手游 对比`
- `小红书 开放世界手游 推荐 避雷`

## Query Groups

- `precise_queries`: platform-specific URL or title patterns.
- `broad_queries`: platform name plus target plus community terms.
- `sentiment_queries`: positive/negative/mixed reception terms.
- `issue_queries`: topic-specific issues, complaints, suggestions, bug, optimization, monetization.
- `category_queries`: generated when no game is known or when category terms are present.
- `comparison_queries`: generated when two or more platforms, games, versions, or competitors are present.
- `trend_queries`: generated for all-platform or time-development tasks.

## Time Filters

If a user says "recently", default to recent 7 days unless the task context indicates another window. Preserve exact user windows such as "最近 30 天", "上个版本", or explicit dates in the parsed task JSON.
