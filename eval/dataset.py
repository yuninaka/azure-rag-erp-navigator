"""golden_qa.jsonl の読み込み。"""

import json
from pathlib import Path
from typing import TypedDict


class GoldenQACase(TypedDict):
    id: str
    category: str
    question: str
    expected_keywords: list[str]


def load_golden_qa(path: Path) -> list[GoldenQACase]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
