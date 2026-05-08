"""Fetch AI task types from Hugging Face Tasks API and format as catalog."""

import json
import argparse
from pathlib import Path

import requests

HF_TASKS_API = "https://huggingface.co/api/tasks"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "catalog" / "raw" / "huggingface_tasks.json"


def fetch_tasks() -> dict:
    """Fetch the complete tasks taxonomy from Hugging Face.

    Returns:
        Dict mapping task_id to task metadata.
    """
    resp = requests.get(HF_TASKS_API, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_task(task_id: str, task_data: dict) -> dict:
    """Format a single task entry into our catalog schema.

    Args:
        task_id: The HF task identifier (e.g., "object-detection").
        task_data: Raw metadata from HF API.

    Returns:
        Formatted dict matching our models.json schema.
    """
    # Extract what we can from HF's structure
    label = task_data.get("label", task_id.replace("-", " ").title())
    description = task_data.get("description", "")
    # Infer category from task_id patterns
    category = infer_category(task_id)

    return {
        "id": task_id,
        "name": label,
        "category": category,
        "task": description[:200] if description else f"{label} task",
        "input": {
            "data_type": infer_input_type(task_id),
            "requirement": "",
        },
        "output": {
            "data_type": infer_output_type(task_id),
            "description": "",
        },
        "source": "Hugging Face Tasks",
    }


def infer_category(task_id: str) -> str:
    """Infer a high-level category from the task ID.

    Args:
        task_id: HF task identifier.

    Returns:
        Category string.
    """
    if task_id.startswith(("text-", "token-", "fill-", "sentence-", "zero-shot")):
        return "自然语言处理"
    if task_id.startswith(("question-answering", "table-question", "document-question")):
        return "自然语言处理"
    if task_id in ("translation", "summarization"):
        return "自然语言处理"
    if task_id.startswith(("image-", "object-", "depth-", "visual-")):
        return "计算机视觉"
    if task_id.startswith("video-"):
        return "视频理解"
    if task_id.startswith(("audio-", "automatic-speech", "voice-")):
        return "音频处理"
    if task_id.startswith("text-to-speech") or task_id.startswith("text-to-audio"):
        return "音频生成"
    if task_id.startswith("text-to-image"):
        return "图像生成"
    if task_id.startswith(("text-to-video", "image-to-video")):
        return "视频生成"
    if task_id in ("reinforcement-learning", "robotics", "agent"):
        return "决策与控制"
    if task_id.startswith(("time-series", "tabular-")):
        return "结构化数据"
    if task_id == "graph-machine-learning":
        return "图数据"
    if task_id in ("multimodal", "feature-extraction", "text-retrieval"):
        return "多模态/通用"
    return "其他"


def infer_input_type(task_id: str) -> str:
    """Infer input data type from task ID.

    Args:
        task_id: HF task identifier.

    Returns:
        Input data type string.
    """
    mapping = {
        "text-": "文本",
        "token-": "文本",
        "fill-": "文本",
        "sentence-": "文本",
        "zero-shot": "文本",
        "translation": "文本",
        "summarization": "文本",
        "question-answering": "文本",
        "image-": "图像",
        "object-": "图像",
        "depth-": "图像",
        "visual-": "图像+文本",
        "document-": "文档图像+文本",
        "video-": "视频",
        "audio-": "音频",
        "automatic-speech": "音频",
        "voice-": "音频",
        "text-to-speech": "文本",
        "text-to-audio": "文本",
        "text-to-image": "文本",
        "text-to-video": "文本",
        "image-to-video": "图像",
        "image-to-image": "图像",
        "reinforcement-learning": "环境状态",
        "robotics": "传感器数据",
        "time-series": "时序数值",
        "tabular-": "表格数据",
        "graph-": "图结构数据",
    }
    for prefix, dtype in mapping.items():
        if task_id.startswith(prefix) or task_id == prefix:
            return dtype
    return "多模态"


def infer_output_type(task_id: str) -> str:
    """Infer output data type from task ID.

    Args:
        task_id: HF task identifier.

    Returns:
        Output data type string.
    """
    mapping = {
        "text-classification": "类别标签",
        "token-classification": "token级标签序列",
        "question-answering": "文本答案",
        "table-question-answering": "文本答案",
        "visual-question-answering": "文本答案",
        "document-question-answering": "文本答案",
        "translation": "文本",
        "summarization": "文本",
        "text-generation": "文本",
        "text2text-generation": "文本",
        "fill-mask": "文本",
        "sentence-similarity": "相似度分数",
        "zero-shot-classification": "类别标签",
        "feature-extraction": "特征向量",
        "text-retrieval": "文档排序",
        "image-classification": "类别标签",
        "image-segmentation": "分割掩码",
        "object-detection": "边界框+类别",
        "video-classification": "类别标签",
        "depth-estimation": "深度图",
        "image-to-image": "图像",
        "image-to-video": "视频",
        "text-to-image": "图像",
        "text-to-video": "视频",
        "automatic-speech-recognition": "文本",
        "audio-classification": "类别标签",
        "text-to-speech": "音频",
        "text-to-audio": "音频",
        "audio-to-audio": "音频",
        "voice-activity-detection": "时间段标注",
        "reinforcement-learning": "动作决策",
        "robotics": "控制信号",
        "time-series-forecasting": "预测数值序列",
        "tabular-classification": "类别标签",
        "tabular-regression": "数值",
        "graph-machine-learning": "节点/边预测",
        "multimodal": "多模态输出",
        "agent": "动作序列",
    }
    return mapping.get(task_id, "结构化输出")


def main():
    parser = argparse.ArgumentParser(description="Fetch AI task types from Hugging Face")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output file path",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: just fetch and print task IDs",
    )
    args = parser.parse_args()

    print("Fetching AI tasks from Hugging Face...")
    raw_tasks = fetch_tasks()
    print(f"Got {len(raw_tasks)} task types")

    if args.test:
        for task_id in sorted(raw_tasks.keys()):
            label = raw_tasks[task_id].get("label", task_id)
            print(f"  {task_id}: {label}")
        return

    formatted = [format_task(tid, tdata) for tid, tdata in raw_tasks.items()]
    formatted.sort(key=lambda x: (x["category"], x["id"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(formatted)} tasks to {args.output}")
    print("\nBy category:")
    categories = {}
    for t in formatted:
        categories.setdefault(t["category"], []).append(t["name"])
    for cat, names in sorted(categories.items()):
        print(f"  {cat}: {len(names)} tasks")


if __name__ == "__main__":
    main()
