"""RAG回答生成に必要なAzureクライアント一式の組み立て。

`eval/run_eval.py`・`src/app/streamlit_app.py`・`scripts/ask_question.py` が
それぞれ個別に組み立てていたAzure OpenAI/AI Search/Cosmos DBクライアントを
共通化し、`generate_answer`の引数を1つにまとめる。
"""

from dataclasses import dataclass

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.config import load_azure_cosmos_config, load_azure_openai_config, load_azure_search_config
from src.session.cosmos_client import get_sessions_container
from src.session.history_manager import SessionHistoryManager


@dataclass(frozen=True)
class RagDependencies:
    openai_client: AzureOpenAI
    embedding_deployment: str
    chat_deployment: str
    search_client: SearchClient
    history_manager: SessionHistoryManager


def build_rag_dependencies() -> RagDependencies:
    """`.env` の設定からRAG回答生成に必要なクライアント一式を組み立てる。"""
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

    return RagDependencies(
        openai_client=openai_client,
        embedding_deployment=openai_config.embedding_deployment,
        chat_deployment=openai_config.chat_deployment,
        search_client=search_client,
        history_manager=history_manager,
    )
