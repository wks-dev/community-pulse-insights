# Report Template

Prefer HTML for final user-facing reports. Markdown is acceptable for quick drafts, CLI output, or systems that ingest Markdown. Do not invent real post links. If no verified URLs exist, move the item to "待验证线索".

## Required Sections

1. 总体结论
2. 样本范围与限制
3. 高频主题
4. 正面玩家意见
5. 负面玩家意见
6. 主要争议点
7. 玩家建议
8. 风险预警
9. 可借鉴设计点
10. 平台差异与舆情发展
11. 证据链接表
12. 待验证线索

## HTML Requirements

The HTML report should be a standalone file with embedded CSS and no external assets. It should include:

- clear title and retrieval date
- summary cards for evidence count, confidence, platforms, and topic count
- sample scope and limitation block
- theme table
- positive and negative opinion sections
- risk table
- platform/trend section for cross-platform reports
- evidence link table with clickable URLs
- pending verification section for URL-less or secondary-only leads

Use semantic HTML (`header`, `main`, `section`, `table`) and keep the design readable for archived intelligence reports.

## Minimal Example

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>游戏社区舆情报告</title>
</head>
<body>
  <header>
    <h1>游戏社区舆情报告：《游戏名》</h1>
    <p>样本边界：公开可检索样本，不代表全量社区舆情。</p>
  </header>
  <main>
    <section id="summary">
      <h2>1. 总体结论</h2>
      <ul>
        <li>样本显示整体情绪为 mixed。[ev_001]</li>
      </ul>
    </section>
    <section id="evidence">
      <h2>11. 证据链接表</h2>
      <table>
        <tr><th>ID</th><th>平台</th><th>标题</th><th>链接</th><th>证据等级</th></tr>
        <tr><td>ev_001</td><td>NGA</td><td><a href="URL">帖子标题</a></td><td>URL</td><td>core</td></tr>
      </table>
    </section>
  </main>
</body>
</html>
```
