# 灵感推荐器 · 项目指南

## 项目概述

AI 硬件产品创意生成器。四维组合（传感器×执行器×载体）+ LLM 生成场景 + 竞品搜索。

## 技术栈

- Python 3.10+
- Claude API（Opus 模型，生成创意）
- xAI Grok API（竞品搜索）
- 纯静态 HTML/JS（展示页面）

## 关键设计决策

- **四维组合**：传感器(1-5)、执行器(1-4)、载体(1-2)随机抽样，AI模型由LLM自行决定
- **追加模式**：results/ideas.json 只追加不覆盖，历史数据不丢失
- **rejection 缓存**：无效组合存入 results/rejected.json，避免重复浪费 token
- **placement 字段**：产品物理位置（穿戴/桌面/墙面/天花板等），位置决定产品形态
- **竞品搜索**：search_similar.py 跳过已搜索的（有 market_research 字段的）

## 常用命令

```bash
# 生成创意
python3 generator/generate.py --sample 20 --batch-size 5 --seed <随机数>

# 搜索竞品
python3 generator/search_similar.py

# 查看结果
cd viewer && python3 -m http.server 8765

# 同步数据到 viewer
cp results/ideas.json viewer/data.json
```

## 环境变量

通过 shell 环境提供：
- `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_DEFAULT_OPUS_MODEL`
- `GROK_API_KEY`

## 注意事项

- generate.py 的 `--seed` 参数控制随机种子，不同 seed 产生不同组合
- xAI API 偶尔超时，search_similar.py 有 3 次重试机制
- viewer/data.json 需要手动从 results/ideas.json 复制更新
- 数据采集脚本（scripts/）依赖外部 API，可能因网站变更而失效
