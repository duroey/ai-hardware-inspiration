# 灵感推荐器 - 设计文档

## 概述

AI硬件产品灵感生成工具。将AI硬件抽象为三元组（传感器 → AI模型 → 执行器），穷举消费级市售组件的排列组合，用 Claude API 为每个组合生成最佳应用场景，帮助发现有市场潜力的产品创意。

## 架构

三层解耦：

```
catalog/（数据目录）→ generator/（生成器）→ viewer/（展示页）
```

## 数据目录（catalog/）

### sensors.json

```json
[
  {
    "id": "camera_rgb",
    "name": "RGB摄像头",
    "category": "视觉",
    "data_type": "图像/视频",
    "source": "Seeed Studio",
    "examples": ["OV2640", "IMX219"]
  }
]
```

### models.json

```json
[
  {
    "id": "cv_image_segmentation",
    "name": "图像语义分割",
    "category": "计算机视觉",
    "task": "将图像中每个像素分类到对应语义类别",
    "input": {
      "data_type": "图像",
      "requirement": "RGB图像，通常需要固定分辨率输入"
    },
    "output": {
      "data_type": "分割掩码",
      "description": "逐像素的类别标注图，可用于区域定位和面积计算"
    }
  }
]
```

### actuators.json

```json
[
  {
    "id": "servo_motor",
    "name": "舵机",
    "category": "机械运动",
    "control_type": "PWM信号",
    "source": "DFRobot",
    "examples": ["SG90", "MG996R"]
  }
]
```

### 数据来源策略

从源头厂商/分销商网站抓取产品目录，确保列表中都是真实可采购的组件。目标厂商包括但不限于：Seeed Studio、DFRobot、SparkFun、Adafruit、Bosch Sensortec、TDK InvenSense 等。

爬取后人工校对，去重归类。

## 生成器（generator/）

### 组合策略

- 全排列：sensors × models × actuators
- 兼容性过滤：传感器 data_type 必须匹配模型 input.data_type，模型 output.data_type 对执行器有驱动意义
- AI 串联不在枚举时限制，交给 LLM 在生成时自行建议

### 分批策略

- 纯机械切片（按固定 batch_size），不按语义分类
- 核心目的：质量验证优先，满意后放量
- 支持 --sample N 试跑、--resume 断点续跑

### CLI 接口

```bash
python generate.py --sample 10          # 试跑看效果
python generate.py --all --resume       # 正式生成，可中断续跑
python generate.py --batch-size 200     # 自定义批大小
```

### Prompt 模板（独立文件 prompt.txt）

为每个组合生成：场景（一句话）、卖点、受众、可行性评分(1-5)。若组合需要串联额外模型则说明，若明显不合理则标记为无意义组合。

### 输出格式

```json
{
  "combination_id": "camera_rgb__cv_object_detection__servo_motor",
  "sensor": "camera_rgb",
  "model": "cv_object_detection",
  "actuator": "servo_motor",
  "scene": "...",
  "selling_point": "...",
  "audience": "...",
  "feasibility": 5,
  "extra_models": null,
  "valid": true,
  "generated_at": "2026-05-08T21:30:00"
}
```

## 展示层（viewer/）

- 单 HTML 文件 + 内嵌 JS，无构建工具
- 加载合并后的 data.json
- 表格视图：传感器、AI模型、执行器、场景、卖点、受众、可行性
- 筛选：按各组件类型多选、按评分范围、排除无意义组合
- 排序：按评分、按名称
- 全文搜索

## 项目结构

```
灵感推荐器/
├── catalog/
│   ├── sensors.json
│   ├── models.json
│   └── actuators.json
├── generator/
│   ├── generate.py
│   ├── prompt.txt
│   ├── combiner.py
│   └── config.yaml
├── results/
│   ├── batch_001.json
│   └── ...
├── viewer/
│   ├── index.html
│   └── data.json
└── scripts/
    └── merge_results.py
```

## 工作流

1. 整理 catalog/（爬取厂商网站 + 人工校对）
2. `python generate.py --sample 10` — 试跑验证效果
3. 调 prompt.txt，反复试跑直到满意
4. `python generate.py --all --resume` — 正式生成
5. `python scripts/merge_results.py` — 合并结果
6. 打开 `viewer/index.html` — 浏览筛选

## 技术选型

- 语言：Python 3.10+
- LLM：Claude API (anthropic SDK)
- 展示：纯静态 HTML/JS
- 数据格式：JSON
- 配置：YAML
