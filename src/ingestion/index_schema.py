"""Azure AI Search インデックススキーマ定義。

チャンク分割方針は Step 2 のインジェストパイプラインで複数パターン（fixed_512 /
fixed_256 / heading_aware、詳細は plans/feat-step1-search-index-design.md 参照）を
比較するため、`chunk_strategy` フィールドで識別できるようにしている。
"""

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large の出力次元数
VECTOR_ALGORITHM_NAME = "erp-hnsw-algorithm"
VECTOR_PROFILE_NAME = "erp-vector-profile"
SEMANTIC_CONFIGURATION_NAME = "erp-semantic-config"


def _build_fields() -> list[SearchField]:
    return [
        SimpleField(name="id", type=SearchFieldDataType.STRING, key=True),
        SearchableField(name="content", analyzer_name="ja.lucene"),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.SINGLE),
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
            searchable=True,
            retrievable=False,
        ),
        SearchableField(name="title", analyzer_name="ja.lucene", filterable=True),
        SimpleField(name="section_path", type=SearchFieldDataType.STRING),
        SimpleField(
            name="source_type", type=SearchFieldDataType.STRING, filterable=True, facetable=True
        ),
        SimpleField(name="source_file", type=SearchFieldDataType.STRING, filterable=True),
        SimpleField(
            name="module_tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.STRING),
            filterable=True,
            facetable=True,
        ),
        SimpleField(name="chunk_index", type=SearchFieldDataType.INT32),
        SimpleField(name="chunk_strategy", type=SearchFieldDataType.STRING, filterable=True),
        SimpleField(
            name="last_updated",
            type=SearchFieldDataType.DATE_TIME_OFFSET,
            filterable=True,
            sortable=True,
        ),
    ]


def _build_vector_search() -> VectorSearch:
    return VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=VECTOR_ALGORITHM_NAME)],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=VECTOR_ALGORITHM_NAME,
            )
        ],
    )


def _build_semantic_search() -> SemanticSearch:
    semantic_config = SemanticConfiguration(
        name=SEMANTIC_CONFIGURATION_NAME,
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
            keywords_fields=[SemanticField(field_name="module_tags")],
        ),
    )
    return SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIGURATION_NAME,
        configurations=[semantic_config],
    )


def build_search_index(index_name: str) -> SearchIndex:
    """ERPナレッジベース用の Azure AI Search インデックス定義を構築する。"""
    return SearchIndex(
        name=index_name,
        fields=_build_fields(),
        vector_search=_build_vector_search(),
        semantic_search=_build_semantic_search(),
    )
