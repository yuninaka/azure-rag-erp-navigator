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

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from eval.dataset import GoldenQACase, load_golden_qa
from eval.metrics import keyword_coverage
from src.config import load_azure_cosmos_config, load_azure_openai_config, load_azure_search_config
from src.ingestion.chunkers import ALL_STRATEGIES
from src.rag.generator import generate_answer
from src.session.cosmos_client import get_sessions_container
from src.session.history_manager import SessionHistoryManager

GOLDEN_QA_PATH = Path(__file__).resolve().parent / "golden_qa.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _build_clients():
    openai_config = load_azure_openai_config()
    search_config = load_azure_search_config()
    cosmos_config = load_azure_cosmos_config()

    openai_client = AzureOpenAI(
        azure_endpoint=openai_config.endpoint,
        api_key=openai_config.api_key,
        api_version=openai_config.api_version,
    )
    search_client = SearchClient(
        search_config.endpoint, search_config.index_name, AzureKeyCredential(search_config.api_key)
    )
    history_manager = SessionHistoryManager(get_sessions_container(cosmos_config))
    return openai_client, openai_config, search_client, history_manager


def _evaluate_case(case: GoldenQACase, strategy: str, clients) -> dict:
    openai_client, openai_config, search_client, history_manager = clients
    session_id = f"eval-{strategy}-{case['id']}-{uuid.uuid4().hex[:6]}"

    result = generate_answer(
        query=case["question"],
        session_id=session_id,
        openai_client=openai_client,
        embedding_deployment=openai_config.embedding_deployment,
        chat_deployment=openai_config.chat_deployment,
        search_client=search_client,
        history_manager=history_manager,
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
    clients = _build_clients()

    all_results: dict[str, list[dict]] = {}
    for strategy in ALL_STRATEGIES:
        print(f"[{strategy}] {len(cases)}問を評価中...")
        results = [_evaluate_case(case, strategy, clients) for case in cases]
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
