from pathlib import Path

from src.ingestion.document_loader import load_source_documents

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dummy_docs"
EXPECTED_DUMMY_DOCUMENT_COUNT = 7


def test_loads_all_dummy_documents_with_expected_source_types() -> None:
    documents = load_source_documents(DATA_DIR)
    source_types = {doc.source_type for doc in documents}

    assert len(documents) == EXPECTED_DUMMY_DOCUMENT_COUNT
    assert source_types == {"manual", "faq", "troubleshooting"}


def test_frontmatter_fields_are_parsed_and_body_excludes_frontmatter() -> None:
    documents = load_source_documents(DATA_DIR)
    initial_setup = next(doc for doc in documents if doc.source_file == "01_initial_setup.md")

    assert initial_setup.title == "初期設定ガイド"
    assert "共通" in initial_setup.module_tags
    assert initial_setup.last_updated == "2026-04-01"
    assert not initial_setup.body.startswith("---")
    assert initial_setup.body.startswith("# 初期設定ガイド")
