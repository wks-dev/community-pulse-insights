# game-news-radar 便携版集成说明

Community Pulse Insights 在 game-news-radar Windows 便携包中以可选旁路模块存在。它不会自动改变新闻采集器的 run-daily.bat，也不会把登录态、Cookie、API Key、原始回复或历史报告打进便携包。

## 目录约定

将本仓库内容放在便携包根目录的 community-pulse-insights/：

~~~text
game-news-radar/
├─ community-pulse-insights/
│  ├─ SKILL.md
│  ├─ references/
│  └─ scripts/
├─ community-pulse-check.bat
└─ community-pulse-prepare.bat
~~~

便携包中使用的两个入口：

~~~bat
community-pulse-check.bat
community-pulse-prepare.bat --run-id company_daily_YYYYMMDD --end-date YYYY-MM-DD --lookback-days 3
~~~

## 运行前提

- Windows 目标电脑安装 Python 3.10+。
- Chrome 或其他受支持浏览器可访问目标 Web AI 页面。
- 操作者手动登录需要使用的 Web AI 页面。
- 不请求、保存、导出或打印密码、Cookie、Token 和浏览器配置。

## 运行产物

任务包和报告默认放在 community-pulse-insights/daily_ai_outputs/<run_id>/：

- prompt_pack.json 和 prompt_pack.md：提示词包。
- raw/：完整 Web AI 原始回复。
- structured/：证据规范化结果。
- reports/index.html：HTML 报告。
- runbook.md：本次运行的人工提交和重渲染步骤。

raw/、structured/、reports/ 和 daily_ai_outputs/ 不应提交到 GitHub，也不应重新打包进发布 zip。

## 兼容性结论

Community Pulse 的 Python 脚本只使用标准库，与 game-news-radar 的 Node.js/npm 依赖不冲突。由于社区采集依赖人工浏览器会话，它不是完全离线步骤；默认新闻采集流程仍然独立运行。

## 来源

本集成说明对应仓库：

https://github.com/wks-dev/community-pulse-insights
