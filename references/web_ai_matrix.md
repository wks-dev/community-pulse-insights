# Web AI Matrix

Use Web AI systems as a discovery and cross-summary layer, not as primary evidence.

## Matrices

- Domestic matrix: `豆包`, `元宝`, `文心一言`, `千问`, `点点`, `知乎直答`
- Global matrix: `Gemini`, `Grok`, `豆包`
- All known AI tools: `Gemini`, `Grok`, `豆包`, `元宝`, `文心一言`, `千问`, `点点`, `知乎直答`

If the user explicitly names AI tools, generate prompts for the named tools. If no tools are named, choose the matrix from platforms and links.

## Platform Routing

Domestic markers route to the domestic matrix:

`douyin`, `抖音`, `xiaohongshu`, `小红书`, `rednote`, `weibo`, `微博`, `bilibili`, `B站`, `哔哩`, `zhihu`, `知乎`, `wechat`, `weixin`, `微信`, `公众号`, `视频号`, `快手`, `kuaishou`, `百度`, `baidu`, `中文网页`, `国内`

Domestic URL markers:

`douyin.com`, `xiaohongshu.com`, `xhslink.com`, `weibo.com`, `bilibili.com`, `b23.tv`, `zhihu.com`, `weixin.qq.com`, `mp.weixin.qq.com`, `kuaishou.com`, `baidu.com`

Global markers route to the global matrix when no domestic platform is in scope:

`youtube`, `ytb`, `twitch`, `x`, `twitter`, `instagram`, `tiktok`, `reddit`, `steam`

## Default URLs

| AI site | URL | Preferred monitoring surfaces |
|---|---|---|
| Gemini | https://gemini.google.com/app | YouTube, Instagram, global web |
| Grok | https://grok.com/ | X, Instagram, real-time global social summary |
| 豆包 | https://www.doubao.com/chat/?channel=browser_landing_page | TikTok, 抖音, 微博, B站, 中文网页 |
| 元宝 | https://yuanbao.tencent.com/chat/naQivTmsDa | 微信生态, 公众号, 新闻, 腾讯系内容, 中文网页 |
| 点点 | https://www.xiaohongshu.com/ai_chat | 小红书, 抖音, 种草内容, 社媒讨论；小红书任务应先打开 https://www.xiaohongshu.com/ 再进入点点 |
| 知乎直答 | https://zhida.zhihu.com/ | 知乎, 问答讨论, 争议复盘, 中文网页 |
| 文心一言 | https://wenxin.baidu.com/ | 百度, 中文网页, 新闻, 贴吧, 百度知道/百科生态 |
| 千问 | https://www.qianwen.com/?bizPassParams=%26x-platform%3DexternalH5 | 中文网页, 新闻, 公开搜索, 社区线索；千问只是执行工具，不是检索对象 |

## Tool Responsibilities

- **Gemini**: global web, YouTube, Instagram-oriented discovery.
- **Grok**: X/Twitter and real-time global social context.
- **豆包**: Chinese web, 抖音, 微博, B站, and TikTok support.
- **元宝**: 微信生态, 公众号, 新闻, 腾讯系内容.
- **点点**: 小红书, 抖音, 种草内容, lifestyle/community discussion. For 小红书 tasks, use the 小红书 page as the entry context before launching 点点; require `xiaohongshu.com` or `xhslink.com` URLs for evidence.
- **知乎直答**: 知乎, Q&A discussion, controversy recap.
- **文心一言**: 百度, 中文网页, 新闻, 贴吧, 百度知道/百科生态.
- **千问**: Chinese web, news, public search, and cross-platform community clues. Use it as a Chinese-web supplemental tool. Qianwen is the execution tool, not the research target; avoid Qwen/Tongyi product pages, API/download pages, and special-tool pages.

## Tool-Name Drift Guardrail

AI tool names are routing labels only. Do not use `千问`, `Qwen`, `通义千问`, `阿里 AI 助手`, `豆包`, `元宝`, `文心一言`, `Gemini`, or `Grok` as search targets unless the user's actual topic is an AI product.

If a Web AI reply returns only the AI tool's own product page, API page, download page, or feature introduction, mark it as `prompt_drift`, retry once with only game/company/community keywords, and do not place that reply in `evidence` or game-community `pending_leads`.

Use `game_name="二游大盘"` only for real market-wide 二游 trends. Failed searches, AI-product pages, or generic no-result replies must not use 二游大盘 as a fallback game name.

## Required Prompt Shape

Ask each Web AI/search assistant to return:

- public URL
- platform
- title
- approximate publish time or discussion time
- visible snippet or accessible excerpt
- short viewpoint summary
- access status
- limitations or uncertainty

No-URL observations must be placed under `待验证线索`.

## Evidence Boundary

Web AI output without URLs must not enter core conclusions. Web AI output with URLs is still only a candidate until the URL is checked, deduplicated, and assigned an evidence level.

Do not use Web AI summaries for:

- unsupported quantitative claims
- direct player quotes without source page access
- private, paywalled, logged-in, or CAPTCHA-protected content
- upgrading inaccessible or URL-less content to core evidence
