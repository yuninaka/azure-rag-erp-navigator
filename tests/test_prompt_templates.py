from src.rag.prompt_templates import build_user_message
from src.rag.search_client import SearchHit

HITS = [
    SearchHit(
        content="テナント作成の手順です。",
        title="初期設定ガイド",
        section_path="初期設定ガイド > テナントの作成",
        source_file="01_initial_setup.md",
        score=1.5,
    ),
    SearchHit(
        content="会計年度の設定手順です。",
        title="会計モジュール設定ガイド",
        section_path="会計モジュール設定ガイド > 勘定科目マスタの登録",
        source_file="04_accounting_setup.md",
        score=1.2,
    ),
]


def test_build_user_message_numbers_context_entries_in_order():
    message = build_user_message("初期設定はどこから始めますか？", HITS)

    assert "[1] 初期設定ガイド > 初期設定ガイド > テナントの作成" in message
    assert (
        "[2] 会計モジュール設定ガイド > 会計モジュール設定ガイド > 勘定科目マスタの登録" in message
    )
    assert message.index("[1]") < message.index("[2]")
    assert "### 質問\n初期設定はどこから始めますか？" in message


def test_build_user_message_with_no_hits_still_includes_question():
    message = build_user_message("質問のみ", [])

    assert "### 質問\n質問のみ" in message
