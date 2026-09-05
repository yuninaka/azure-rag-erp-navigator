"""ダミー業務文書のチャンク化・埋め込み生成・Azure AI Search 投入パイプライン。

同一インデックス内で複数のチャンク分割方針を `chunk_strategy` フィールドで
共存させる設計（plans/feat-step1-search-index-design.md 参照）。評価時は
`$filter=chunk_strategy eq '...'` で方針ごとの精度を比較する想定。
"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.config import load_azure_openai_config, load_azure_search_config
from src.ingestion.chunkers import ALL_STRATEGIES, chunk_by_strategy
from src.ingestion.document_loader import SourceDocument, load_source_documents
from src.ingestion.embed import embed_texts

EmbedFn = Callable[[list[str]], list[list[float]]]


def _document_id(source_file: str, strategy: str, chunk_index: int) -> str:
    stem = Path(source_file).stem
    return f"{stem}-{strategy}-{chunk_index}"


def _to_datetimeoffset(date_str: str) -> str:
    return datetime.fromisoformat(date_str).replace(tzinfo=UTC).isoformat()


def build_search_documents(
    documents: list[SourceDocument],
    strategy: str,
    embed_fn: EmbedFn,
) -> list[dict]:
    """`documents` を指定戦略でチャンク化し、埋め込み付きのSearch投入用ドキュメントを作る。"""
    chunks_by_doc = [(doc, chunk_by_strategy(doc.body, strategy)) for doc in documents]
    all_texts = [chunk.content for _, chunks in chunks_by_doc for chunk in chunks]
    vectors = embed_fn(all_texts)

    search_documents = []
    vector_index = 0
    for doc, chunks in chunks_by_doc:
        for chunk in chunks:
            search_documents.append(
                {
                    "id": _document_id(doc.source_file, strategy, chunk.chunk_index),
                    "content": chunk.content,
                    "content_vector": vectors[vector_index],
                    "title": doc.title,
                    "section_path": chunk.section_path,
                    "source_type": doc.source_type,
                    "source_file": doc.source_file,
                    "module_tags": doc.module_tags,
                    "chunk_index": chunk.chunk_index,
                    "chunk_strategy": strategy,
                    "last_updated": _to_datetimeoffset(doc.last_updated),
                }
            )
            vector_index += 1
    return search_documents


def run_ingestion(data_dir: Path, strategies: list[str] | None = None) -> dict[str, int]:
    """全戦略（または指定戦略）でダミー文書をインデックスに投入し、戦略ごとの成功件数を返す。"""
    strategies = strategies or ALL_STRATEGIES
    openai_config = load_azure_openai_config()
    search_config = load_azure_search_config()

    openai_client = AzureOpenAI(
        azure_endpoint=openai_config.endpoint,
        api_key=openai_config.api_key,
        api_version=openai_config.api_version,
    )
    search_client = SearchClient(
        search_config.endpoint,
        search_config.index_name,
        AzureKeyCredential(search_config.api_key),
    )

    def embed_fn(texts: list[str]) -> list[list[float]]:
        return embed_texts(openai_client, openai_config.embedding_deployment, texts)

    documents = load_source_documents(data_dir)
    uploaded_counts: dict[str, int] = {}
    for strategy in strategies:
        search_documents = build_search_documents(documents, strategy, embed_fn)
        results = search_client.upload_documents(search_documents)
        uploaded_counts[strategy] = sum(1 for result in results if result.succeeded)
    return uploaded_counts
