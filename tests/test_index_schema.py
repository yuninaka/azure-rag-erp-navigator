from azure.search.documents.indexes.models import SearchFieldDataType

from src.ingestion.index_schema import (
    EMBEDDING_DIMENSIONS,
    SEMANTIC_CONFIGURATION_NAME,
    VECTOR_PROFILE_NAME,
    build_search_index,
)


def test_index_has_expected_field_names_and_key() -> None:
    index = build_search_index("erp-knowledge-index")
    field_names = {f.name for f in index.fields}

    assert index.name == "erp-knowledge-index"
    assert field_names == {
        "id",
        "content",
        "content_vector",
        "title",
        "section_path",
        "source_type",
        "source_file",
        "module_tags",
        "chunk_index",
        "chunk_strategy",
        "last_updated",
    }
    key_fields = [f for f in index.fields if f.key]
    assert len(key_fields) == 1
    assert key_fields[0].name == "id"


def test_content_vector_field_matches_embedding_model_dimensions() -> None:
    index = build_search_index("erp-knowledge-index")
    vector_field = next(f for f in index.fields if f.name == "content_vector")

    assert vector_field.type == SearchFieldDataType.Collection(SearchFieldDataType.SINGLE)
    assert vector_field.vector_search_dimensions == EMBEDDING_DIMENSIONS
    assert vector_field.vector_search_profile_name == VECTOR_PROFILE_NAME


def test_vector_search_profile_and_algorithm_are_linked() -> None:
    index = build_search_index("erp-knowledge-index")
    profile = index.vector_search.profiles[0]
    algorithm = index.vector_search.algorithms[0]

    assert profile.name == VECTOR_PROFILE_NAME
    assert profile.algorithm_configuration_name == algorithm.name


def test_semantic_configuration_uses_title_content_and_keywords_fields() -> None:
    index = build_search_index("erp-knowledge-index")
    semantic_config = index.semantic_search.configurations[0]

    assert index.semantic_search.default_configuration_name == SEMANTIC_CONFIGURATION_NAME
    assert semantic_config.prioritized_fields.title_field.field_name == "title"
    assert [f.field_name for f in semantic_config.prioritized_fields.content_fields] == ["content"]
    assert [f.field_name for f in semantic_config.prioritized_fields.keywords_fields] == [
        "module_tags"
    ]


def test_filterable_fields_support_faceted_navigation() -> None:
    index = build_search_index("erp-knowledge-index")
    filterable_names = {f.name for f in index.fields if f.filterable}

    assert filterable_names == {
        "title",
        "source_type",
        "source_file",
        "module_tags",
        "chunk_strategy",
        "last_updated",
    }
