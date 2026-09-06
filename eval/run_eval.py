"""golden_qaでチャンク分割方針ごとのRAG回答精度（キーワード網羅率）を評価する。

各質問を3つのチャンク分割方針（fixed_512 / fixed_256 / heading_aware）それぞれで
実行し、`generate_answer`（本番と同じ回答生成ロジック）に通した結果を採点する。
評価用のセッションは質問ごとに使い捨てにし、通常の会話履歴とは混ざらないようにしている。
"""

import json
import statistics
import sys
import uuid
from pathlib import Path
from typing import Any

from eval.dataset import GoldenQACase, load_golden_qa
from eval.metrics import keyword_coverage
from src.ingestion.chunkers import ALL_STRATEGIES
from src.rag.dependencies import RagDependencies, build_rag_dependencies
from src.rag.generator import generate_answer

GOLDEN_QA_PATH = Path(__file__).resolve().parent / "golden_qa.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _evaluate_case(case: GoldenQACase, strategy: str, deps: RagDependencies) -> dict[str, Any]:
    session_id = f"eval-{strategy}-{case['id']}-{uuid.uuid4().hex[:6]}"

    result = generate_answer(
        query=case["question"],
        session_id=session_id,
        deps=deps,
        chunk_strategy=strategy,
    )
    score = keyword_coverage(result.answer, case["expected_keywords"])
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "expected_keywords": case["expected_keywords"],
        "answer": result.answer,
        "score": score,
    }


def main() -> int:
    cases = load_golden_qa(GOLDEN_QA_PATH)
    deps = build_rag_dependencies()

    all_results: dict[str, list[dict[str, Any]]] = {}
    for strategy in ALL_STRATEGIES:
        print(f"[{strategy}] {len(cases)}問を評価中...")
        results = [_evaluate_case(case, strategy, deps) for case in cases]
        all_results[strategy] = results
        avg = statistics.mean(r["score"] for r in results)
        print(f"  平均スコア: {avg:.2f}")
        for r in results:
            print(f"    {r['id']} ({r['category']}): {r['score']:.2f}")

    RESULTS_PATH.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n詳細結果を {RESULTS_PATH} に保存しました。")

    print("\n=== 戦略別サマリー ===")
    for strategy, results in all_results.items():
        avg = statistics.mean(r["score"] for r in results)
        print(f"{strategy}: {avg:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
