# Community Pulse Insights

面向米哈游、库洛及二次元游戏社区的舆情监测与报告生成 Skill。项目把公开网页检索、Web AI 原始输出、证据规范化和 HTML 报告生成串成可复用流程。

本仓库同时提供与 game-news-radar 游戏媒体新闻采集器的便携版集成说明。两者职责不同：game-news-radar 负责新闻来源采集，Community Pulse 负责社区舆情分析；集成后仍保持可选旁路，不会改变新闻采集器的默认流程。

## 项目内容

- SKILL.md：Skill 主说明和工作流入口。
- references/：平台采集、证据规则、报告结构和故障处理参考。
- scripts/：任务解析、提示词生成、原始输出整理、证据合并和 HTML 报告脚本。
- agents/openai.yaml：Agent 配置。
- VERSION：当前 Skill 版本。
- PORTABLE_INTEGRATION.md：与 game-news-radar 便携版的集成边界、入口和验证方式。

## 使用方式

1. 阅读 SKILL.md，按任务选择单游戏、公司/赛道日报或游戏名单轮询模式。
2. 使用 scripts/build_company_daily_pack.py 或 scripts/run_company_daily_pipeline.py 生成提示词包和运行目录。
3. 操作者在目标 Web AI 页面手动完成登录，再提交提示词并保存完整原始回复。
4. 使用 robust_structure_raw.py 进行证据规范化，再使用对应的 render_*_report.py 生成 HTML 报告。

公司/赛道日报示例：

~~~powershell
python scripts/run_company_daily_pipeline.py --run-id company_daily_YYYYMMDD --output-root daily_ai_outputs --end-date YYYY-MM-DD --lookback-days 3
~~~

游戏名单轮询示例：

~~~powershell
python scripts/run_game_polling_pipeline.py path/to/game_list.xlsx --output-root daily_ai_outputs
~~~

## 与便携版集成

如果你使用 game-news-radar 的 Windows 便携包，请将本仓库内容放在其根目录下的 community-pulse-insights/。便携包中的 community-pulse-check.bat 用于检查文件完整性，community-pulse-prepare.bat 用于生成一次任务包和 runbook。

Community Pulse 使用 Python 标准库，目标电脑需要 Python 3.10+。新闻采集器的便携 Node.js、node_modules、Chrome 路径和 DeepSeek 配置不属于本仓库的运行依赖。便携版二进制包和运行产物应单独分发，不应提交到本仓库。

详见 PORTABLE_INTEGRATION.md。

## 证据和访问边界

- 只处理公开可访问内容，不绕过登录、验证码、403、付费墙、速率限制或私有群组。
- 操作者必须自己登录目标网站；不要把密码、Cookie、Token 或浏览器配置写入仓库。
- Web AI 摘要不能自动替代原始 URL 证据。
- 核心结论必须有原始 URL；无 URL 的内容只能作为辅助样本或待验证线索。
- 报告必须说明样本范围、抓取时间、置信度和证据限制。
- raw/、structured/、reports/ 和 daily_ai_outputs/ 仅用于运行时，不应提交到版本库。

## 版本说明

当前版本见 VERSION。这个仓库是稳定版工作流的隔离预览分支，用于验证采集可靠性改进；如需对比或回滚，请保留独立运行目录，不要覆盖其他 Skill 版本。
