# 灵感推荐器

AI 硬件产品创意生成器。通过排列组合传感器、执行器、载体，用大模型生成有商业价值的产品创意，并搜索市面竞品判断市场机会。

## 核心思路

将 AI 硬件产品抽象为四维组合：

```
传感器(1-5个) × 执行器(1-4个) × 载体(1-2个) → LLM 生成产品创意 + 推荐 AI 模型
```

- **传感器**：51 种类型（摄像头、温湿度、气体、距离、雷达等）
- **执行器**：42 种类型（舵机、电机、显示屏、LED、继电器等）
- **载体**：1560 个品类（日用品、电器、穿戴、家具、工具等）
- **AI 模型**：不预设，由 LLM 根据组合自行推荐最佳 AI pipeline

## 使用

```bash
# 安装依赖
pip install -r requirements.txt

# 生成创意（随机抽 10 个组合）
python3 generator/generate.py --sample 10 --batch-size 5

# 换随机种子再来一批
python3 generator/generate.py --sample 20 --batch-size 5 --seed 666

# 搜索竞品（对未搜索的创意补充市场调研）
python3 generator/search_similar.py

# 查看结果（启动本地服务器）
cd viewer && python3 -m http.server 8765
# 浏览器打开 http://localhost:8765
```

## 项目结构

```
├── catalog/                    # 数据目录
│   ├── raw/                   # 原始数据
│   │   ├── seeed/            # Seeed Studio 产品（Typesense API）
│   │   ├── dfrobot/          # DFRobot 产品（/api/main/product/search）
│   │   ├── huggingface_tasks.json  # 47 种 AI 任务类型
│   │   └── jd_carriers.json  # 1560 个载体品类（京东品类树）
│   ├── classified_sensors.json    # 51 种传感器类型（LLM 分类合并）
│   └── classified_actuators.json  # 42 种执行器类型（LLM 分类合并）
├── generator/
│   ├── generate.py            # 主生成脚本（Claude Opus）
│   ├── search_similar.py      # 竞品搜索（xAI Grok）
│   ├── prompt.txt             # Prompt 模板
│   └── config.yaml
├── results/
│   ├── ideas.json             # 累积的有效创意（追加模式）
│   └── rejected.json          # 无效组合缓存（避免重复）
├── viewer/
│   ├── index.html             # 展示页面（表格+筛选+搜索）
│   └── data.json              # 展示用数据副本
└── scripts/                   # 数据采集脚本
    ├── scrape_seeed.py        # Seeed Studio 爬虫
    ├── scrape_dfrobot.py      # DFRobot 爬虫
    ├── fetch_ai_models.py     # HuggingFace 任务获取
    ├── fetch_carriers.py      # 京东品类树获取
    └── classify_products.py   # LLM 批量分类
```

## 环境变量

```bash
# Claude API（生成创意）
ANTHROPIC_AUTH_TOKEN=xxx
ANTHROPIC_BASE_URL=xxx
ANTHROPIC_DEFAULT_OPUS_MODEL=xxx

# xAI Grok API（竞品搜索）
GROK_API_KEY=xxx
```

## Pipeline

```
数据采集 → LLM分类 → 随机组合 → LLM生成创意 → 竞品搜索 → 展示页面
                                      ↓
                               rejected缓存（避免重复）
```

每次 `generate.py` 运行：
1. 从四维数据中随机抽样（传感器1-5 × 执行器1-4 × 载体1-2）
2. 跳过已知无效组合（rejected.json）
3. 送入 Claude Opus 判断有效性 + 生成产品创意
4. 有效创意追加到 ideas.json，无效组合存入 rejected 缓存

## 数据来源

| 维度 | 来源 | 方式 |
|------|------|------|
| 传感器 | Seeed Studio + DFRobot | API 爬取 → LLM 分类合并 |
| 执行器 | Seeed Studio + DFRobot | API 爬取 → LLM 分类合并 |
| 载体 | 京东品类树（第三层） | API 获取 → 人工清洗 |
| AI 模型 | 不预设 | LLM 根据组合自行推荐 |
