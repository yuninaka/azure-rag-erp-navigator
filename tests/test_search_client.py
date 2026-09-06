from src.ingestion.chunkers import FIXED_512, HEADING_AWARE
from src.rag.search_client import DEFAULT_TOP_K, SearchHit, hybrid_search


class _FakeSearchClient:
    def __init__(self, results: list[dict]):
        self._results = results
        self.last_call_kwargs: dict | None = None

    def search(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._results


RAW_RESULT = {
    "content": "テナント作成の手順です。",
    "title": "初期設定ガイド",
    "section_path": "初期設定ガイド > テナントの作成",
    "source_file": "01_initial_setup.md",
    "@search.score": 2.34,
}


def test_hybrid_search_maps_raw_results_to_search_hits():
    client = _FakeSearchClient([RAW_RESULT])

    hits = hybrid_search(client, "テナント作成の手順", [0.1, 0.2, 0.3])

    assert hits == [
        SearchHit(
            content="テナント作成の手順です。",
            title="初期設定ガイド",
            section_path="初期設定ガイド > テナントの作成",
            source_file="01_initial_setup.md",
            score=2.34,
        )
    ]


def test_hybrid_search_uses_hybrid_query_with_default_strategy_and_top():
    client = _FakeSearchClient([])

    hybrid_search(client, "質問", [0.1, 0.2])

    kwargs = client.last_call_kwargs
    assert kwargs["search_text"] == "質問"
    assert kwargs["query_type"] == "semantic"
    assert kwargs["filter"] == f"chunk_strategy eq '{HEADING_AWARE}'"
    assert kwargs["top"] == DEFAULT_TOP_K
    assert len(kwargs["vector_queries"]) == 1
    assert kwargs["vector_queries"][0].vector == [0.1, 0.2]
    assert kwargs["vector_queries"][0].fields == "content_vector"


def test_hybrid_search_respects_custom_chunk_strategy_and_top():
    client = _FakeSearchClient([])

    hybrid_search(client, "質問", [0.1], top=3, chunk_strategy=FIXED_512)

    kwargs = client.last_call_kwargs
    assert kwargs["filter"] == f"chunk_strategy eq '{FIXED_512}'"
    assert kwargs["top"] == 3
    assert kwargs["vector_queries"][0].k_nearest_neighbors == 3
