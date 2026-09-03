# 文心一言适配记录

## 正确入口

- 入口地址：`https://wenxin.baidu.com/`
- 不使用产品介绍页：`https://wenxin.baidu.com/home`
- 不进入专项工具页：魔法图片、写作帮手、放心写、AI 生图、AI PPT 等。
- 正确目标是普通文字对话页。

## 普通对话页身份特征

- URL 主机为 `wenxin.baidu.com`，路径可为 `/` 或发送后的 `/search/...`。
- 页面出现普通对话特征：`开启新对话`、`文心5.1`、`我已准备好`、普通 textarea 输入框。
- 登录状态判断：页面出现账号脱敏文本，例如 `178******82`，且没有登录页、验证码、权限错误。

## 2026-07-24 L5 测试结果

- 测试编号：`WENXINACK20260724001`
- 入口 URL：`https://wenxin.baidu.com/`
- 发送后 URL：`https://wenxin.baidu.com/search/10285416163203770406?enter_type=chat_url`
- 页面标题：`百度文心助手 - 办公学习一站解决`
- 最终等级：`L5`
- 回复完整文字：`WENXINACK20260724001`
- 结果 JSON：`D:/石声未来项目文件/游戏情报快讯/daily_ai_outputs/adapter_tests_20260724/wenxin_final_result.json`
- 截图路径：`D:/石声未来项目文件/游戏情报快讯/daily_ai_outputs/adapter_tests_20260724/wenxin_l5_result.png`

## 新建对话

- 主定位器：`.new-dialog-container-button:has-text("开启新对话")`
- 备用方式：打开 `https://wenxin.baidu.com/` 并确认输入框为空、对话区无上一轮提示词。
- 如果进入 `/home`、下载页或专项工具页，应返回根页面并重新确认普通文字对话特征。

## 输入框

- 主定位器：`textarea#chat-textarea.ci-textarea`
- 备用定位器：
  - `textarea.ci-textarea`
  - `textarea`
- 候选数量要求：优先唯一可见普通文字输入框。
- 清空方法：点击输入框 -> `Ctrl+A` -> `Backspace` -> 读取 `textarea.value`，确认为空。
- 禁止把搜索框、图片提示框、文件上传区或专项工具输入框当作普通对话输入框。

## 发送按钮

- 主定位器：`#ci-submit-button-ai.ci-submit-button-ai-active`
- 备用定位器：`span.ci-submit-button img#ci-submit-button-ai`
- 发送前必须确认按钮可见、可点击、未被遮挡。
- 不能以输入框清空作为发送成功依据。

## 用户消息

- 主定位器：`#conversation-flow-content .conversation-flow-question-container`
- 备用定位器：
  - `.cs-question-bubble`
  - `.cs-question-pure-text`
- 成功标准：新增用户消息出现在普通问答区，包含本轮唯一测试编号和本轮提示词。

## AI 回复

- 主定位器：`#conversation-flow-content .conversation-flow-answer-container`
- 备用定位器：
  - `.answer-box.last-answer-box`
  - `.cs-answer-container .cosd-markdown`
  - `.marklang-paragraph`
- 成功标准：本轮用户消息之后出现新的 AI 回复，回复文本包含本轮唯一测试编号。

## 流式输出完成判断

- 未发现 `停止生成`、`生成中`、`正在回答`、`暂停` 等状态文本。
- 回复节点文本在轮询中稳定。
- 发送按钮或输入区恢复可用时可作为辅助判断。

## 超时与失败恢复

- 页面身份不对：返回 `https://wenxin.baidu.com/`，避免 `/home` 和专项工具页。
- 未登录：停止并提示用户在内置浏览器登录，不读取或导出凭据。
- 输入框不唯一：结合页面区域、父级 `.ci-root` / `.ci-container` / `chat-input-box-pc` 和发送按钮判断。
- 发送后未出现用户消息：标记发送未确认，不重复盲点。
- 回复未出现或无法区分历史内容：标记回复未确认。
- 禁止使用固定屏幕坐标。

## 2026-07-29 v0.4.4 采集修复

已观察问题：返回 `https://wenxin.baidu.com/` 后，普通输入框可能延迟出现；如果只等待 3 秒，会误判 `textarea#chat-textarea.ci-textarea` 不存在。

当前规则：

1. 先打开 `https://wenxin.baidu.com/`，必要时点击唯一可见的“开启新对话”。
2. 等待 `textarea#chat-textarea.ci-textarea` 最长 45 秒。
3. 仍要求唯一可见输入框和唯一可见启用的 `#ci-submit-button-ai.ci-submit-button-ai-active`。
4. 只发送文心安全短 prompt，不携带 Grok、Gemini、X/Twitter、YouTube、跨境访问等词。
5. 如果 textarea 仍不出现，记录平台限制，不切换到泛用 textarea。
