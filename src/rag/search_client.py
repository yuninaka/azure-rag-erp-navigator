"""Azure AI Search に対するハイブリッド検索（ベクトル+キーワード+セマンティックランカー）。"""

from dataclasses import dataclass

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from src.config import AzureSearchConfig
from src.ingestion.chunkers import HEADING_AWARE
from src.ingestion.index_schema import SEMANTIC_CONFIGURATION_NAME

DEFAULT_TOP_K = 5
# チャット応答ではheading_awareを既定戦略とする（見出し単位で意味のまとまりが保たれ、
# 引用元のsection_pathも直感的になるため）。fixed_512/fixed_256はStep6のgolden_qa評価で
# chunk_strategyを切り替えて比較する。
DEFAULT_CHUNK_STRATEGY = HEADING_AWARE


@dataclass(frozen=True)
class SearchHit:
    content: str
    title: str
    section_path: str
    source_file: str
    score: float


def build_search_client(config: AzureSearchConfig) -> SearchClient:
    return SearchClient(config.endpoint, config.index_name, AzureKeyCredential(config.api_key))


def hybrid_search(
    client: SearchClient,
    query_text: str,
    query_vector: list[float],
    *,
    top: int = DEFAULT_TOP_K,
    chunk_strategy: str = DEFAULT_CHUNK_STRATEGY,
) -> list[SearchHit]:
    """ベクトル検索・キーワード検索・セマンティックランカーを1リクエストで実行する。"""
    results = client.search(
        search_text=query_text,
        vector_queries=[
            VectorizedQuery(vector=query_vector, k_nearest_neighbors=top, fields="content_vector")
        ],
        filter=f"chunk_strategy eq '{chunk_strategy}'",
        query_type="semantic",
        semantic_configuration_name=SEMANTIC_CONFIGURATION_NAME,
        select=["content", "title", "section_path", "source_file"],
        top=top,
    )
    return [
        SearchHit(
            content=result["content"],
            title=result["title"],
            section_path=result["section_path"],
            source_file=result["source_file"],
            score=result["@search.score"],
        )
        for result in results
    ]
