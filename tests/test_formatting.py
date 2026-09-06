from src.app.formatting import format_citations_markdown
from src.session.history_manager import Citation


def test_format_citations_markdown_numbers_entries_in_order():
    citations = [
        Citation(
            title="初期設定ガイド",
            section_path="初期設定ガイド > テナントの作成",
            source_file="01_initial_setup.md",
        ),
        Citation(
            title="会計モジュール設定ガイド",
            section_path="会計モジュール設定ガイド > 勘定科目マスタの登録",
            source_file="04_accounting_setup.md",
        ),
    ]

    markdown = format_citations_markdown(citations)

    assert markdown == (
        "- [1] 初期設定ガイド > テナントの作成 (01_initial_setup.md)\n"
        "- [2] 会計モジュール設定ガイド > 勘定科目マスタの登録 (04_accounting_setup.md)"
    )


def test_format_citations_markdown_with_no_citations_returns_empty_string():
    assert format_citations_markdown([]) == ""
