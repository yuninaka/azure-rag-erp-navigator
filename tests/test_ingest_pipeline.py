from src.ingestion.chunkers import FIXED_512
from src.ingestion.document_loader import SourceDocument
from src.ingestion.ingest_pipeline import build_search_documents

SAMPLE_DOCUMENTS = [
    SourceDocument(
        title="サンプルガイド",
        module_tags=["共通"],
        last_updated="2026-04-01",
        source_type="manual",
        source_file="01_sample.md",
        body="# サンプルガイド\n\n本文です。",
    )
]


def _fake_embed_fn(texts: list[str]) -> list[list[float]]:
    return [[float(len(text))] for text in texts]


def test_build_search_documents_shapes_fields_for_search_index() -> None:
    documents = build_search_documents(SAMPLE_DOCUMENTS, FIXED_512, _fake_embed_fn)

    assert len(documents) == 1
    doc = documents[0]
    assert doc["id"] == "01_sample-fixed_512-0"
    assert doc["title"] == "サンプルガイド"
    assert doc["source_type"] == "manual"
    assert doc["source_file"] == "01_sample.md"
    assert doc["module_tags"] == ["共通"]
    assert doc["chunk_strategy"] == FIXED_512
    assert doc["chunk_index"] == 0
    assert doc["last_updated"] == "2026-04-01T00:00:00+00:00"
    assert doc["content_vector"] == [float(len(doc["content"]))]


def test_build_search_documents_assigns_embeddings_in_chunk_order() -> None:
    two_docs = SAMPLE_DOCUMENTS + [
        SourceDocument(
            title="サンプルガイド2",
            module_tags=["会計"],
            last_updated="2026-04-02",
            source_type="manual",
            source_file="02_sample.md",
            body="# サンプルガイド2\n\n2つ目の本文です。",
        )
    ]

    documents = build_search_documents(two_docs, FIXED_512, _fake_embed_fn)

    assert [d["source_file"] for d in documents] == ["01_sample.md", "02_sample.md"]
    assert all(d["content_vector"] == [float(len(d["content"]))] for d in documents)
