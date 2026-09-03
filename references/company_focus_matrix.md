# Company Focus Matrix

Use this matrix for daily company-level game-community intelligence when the user wants a 二游日报 focused on 米哈游, 库洛, or the broader 二游 market.

## Default Window

- Daily report lookback: most recent 3 days.
- First baseline or weekly report: pass `--lookback-days 7` explicitly.
- If an item happened earlier but discussion is active inside the 3-day window, keep it only when the evidence URL or visible discussion timestamp supports current activity.

## MiHoYo / HoYoverse Products

| company | game_name | aliases | product_tier | game_status | daily_policy |
|---|---|---|---|---|---|
| 米哈游 | FlyMe2theMoon | FlyMe2theMoon | history_context | 早期独立游戏，历史产品 | Only return when tied to brand history, anniversary, IP context, or current discussion. |
| 米哈游 | 崩坏学园 | Zombiegal Kawaii; Houkai Gakuen | history_context | 早期历史产品 | Only return when tied to brand history, anniversary, IP context, or current discussion. |
| 米哈游 | 崩坏学园2 | Houkai Gakuen 2 | daily_focus | 已上线、持续运营 | Monitor version, events, welfare, payment, comeback, churn, and long-service sentiment. |
| 米哈游 | 崩坏3 | Honkai Impact 3rd | daily_focus | 已上线、持续运营 | Monitor version, characters, story, payment, operation, and veteran-player sentiment. |
| 米哈游 | 未定事件簿 | Tears of Themis | daily_focus | 已上线、持续运营 | Monitor events, cards, female-oriented community sentiment, payment, and story feedback. |
| 米哈游 | 原神 | Genshin Impact | daily_focus | 已上线、持续运营 | Monitor version, characters, story, exploration, events, optimization, community controversy, and competitor comparison. |
| 米哈游 | 崩坏：星穹铁道 | Honkai: Star Rail; HSR | daily_focus | 已上线、持续运营 | Monitor version, characters, story, relics, endgame, gacha/payment, and player retention. |
| 米哈游 | 绝区零 | Zenless Zone Zero; ZZZ | daily_focus | 已上线、持续运营 | Monitor version, characters, combat, story, operation, optimization, and retention/churn. |
| 米哈游 | 崩坏：因缘精灵 | Honkai: Nexus Anima | research_watch | 正在进行“进化测试” | Return when there is public test, recruitment, preview, leak, reservation, or discussion evidence. |
| 米哈游 | 星布谷地 | Petit Planet | research_watch | 已完成多轮封闭测试，继续研发和预约 | Return when there is public test, recruitment, preview, leak, reservation, or discussion evidence. |
| 米哈游 | Varsapura | 雨之城 | research_watch | 已开启首轮保密测试招募 | Return when there is public recruitment, preview, leak, reservation, or discussion evidence. |

## Kuro Games Products

| company | game_name | aliases | product_tier | game_status | daily_policy |
|---|---|---|---|---|---|
| 库洛 | 鸣潮 | Wuthering Waves; WuWa | daily_focus | 已上线、持续运营 | Monitor version, characters, combat, story, optimization, compensation, community controversy, and competitor comparison. |
| 库洛 | 战双帕弥什 | Punishing: Gray Raven; PGR | daily_focus | 已上线、持续运营 | Monitor version, characters, combat design, story, welfare, payment, veteran sentiment, and operation rhythm. |

## Company-Level Signals

Return company-level items even when they are not tied to a single product if they affect player trust, market position, or community risk:

- Version cadence and content drought.
- Operation, compensation, welfare, or communication disputes.
- Recruitment, test news, project leaks, or product roadmap signals.
- Cross-game player migration, comeback, churn, or payment hesitation.
- Competitor comparison across 米哈游, 库洛, 鹰角, 叠纸, 网易, 腾讯, B站, 完美世界, and other 二游 publishers.

## Product Tier Rules

- `daily_focus`: eligible for every daily scan.
- `research_watch`: return only if there is recent public evidence or active discussion.
- `history_context`: return only if it explains a current event, brand/IP discussion, anniversary, nostalgia wave, or controversy.
- `market`: use for 二游大盘 items that are not specific to one product.

## Event Scoring

Use this lightweight score to decide what enters the top section:

| condition | score |
|---|---:|
| URL-backed evidence | +3 |
| High-risk sentiment or controversy | +3 |
| Company-level trust, operation, or roadmap signal | +3 |
| `daily_focus` product | +2 |
| `research_watch` product with new public evidence | +2 |
| Multi-platform repetition | +2 |
| Clear player intent: 入坑 / 回流 / 退坑 / 观望 / 抽卡 / 付费 | +2 |
| Specific player suggestions or actionable design feedback | +1 |
| `history_context` item without current relevance | -3 |

Do not include items without a URL in the core score. Put them into pending leads.

