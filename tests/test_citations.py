from src.rag.citations import build_citations
from src.rag.search_client import SearchHit
from src.session.history_manager import Citation


def test_build_citations_maps_search_hits_to_citation_objects() -> None:
    hits = [
        SearchHit(
            content="本文",
            title="初期設定ガイド",
            section_path="初期設定ガイド > テナントの作成",
            source_file="01_initial_setup.md",
            score=2.1,
        )
    ]

    citations = build_citations(hits)

    assert citations == [
        Citation(
            title="初期設定ガイド",
            section_path="初期設定ガイド > テナントの作成",
            source_file="01_initial_setup.md",
        )
    ]


def test_build_citations_with_no_hits_returns_empty_list() -> None:
    assert build_citations([]) == []
