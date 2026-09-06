"""RAG回答生成の動作確認用CLI。1つの質問に対する回答と引用元を表示する。

使い方: uv run python scripts/ask_question.py "質問文" [session_id]
"""

import sys
import uuid

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.config import load_azure_cosmos_config, load_azure_openai_config, load_azure_search_config
from src.rag.generator import generate_answer
from src.session.cosmos_client import get_sessions_container
from src.session.history_manager import SessionHistoryManager


def main() -> int:
    if len(sys.argv) < 2:
        print('使い方: uv run python scripts/ask_question.py "質問文" [session_id]')
        return 1
    query = sys.argv[1]
    session_id = sys.argv[2] if len(sys.argv) > 2 else f"cli-{uuid.uuid4().hex[:8]}"

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

    result = generate_answer(
        query=query,
        session_id=session_id,
        openai_client=openai_client,
        embedding_deployment=openai_config.embedding_deployment,
        chat_deployment=openai_config.chat_deployment,
        search_client=search_client,
        history_manager=history_manager,
    )

    print(f"session_id: {session_id}")
    print(f"\n回答:\n{result.answer}")
    print("\n引用元:")
    for i, citation in enumerate(result.citations, start=1):
        print(f"  [{i}] {citation.section_path} ({citation.source_file})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
