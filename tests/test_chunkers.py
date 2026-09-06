import pytest
import tiktoken

from src.ingestion.chunkers import (
    FIXED_256,
    FIXED_512,
    HEADING_AWARE,
    chunk_by_strategy,
    chunk_fixed,
    chunk_heading_aware,
)

_ENCODING = tiktoken.get_encoding("cl100k_base")

SAMPLE_MARKDOWN = """# タイトル
イントロ文です。

## セクションA
セクションAの本文。

### サブセクションA-1
サブセクションA-1の本文。

## セクションB
セクションBの本文。
"""


def test_heading_aware_splits_by_heading_with_nested_section_path() -> None:
    chunks = chunk_heading_aware(SAMPLE_MARKDOWN)

    assert [c.section_path for c in chunks] == [
        "タイトル",
        "タイトル > セクションA",
        "タイトル > セクションA > サブセクションA-1",
        "タイトル > セクションB",
    ]
    assert [c.chunk_index for c in chunks] == [0, 1, 2, 3]
    assert all(c.chunk_strategy == HEADING_AWARE for c in chunks)
    assert chunks[0].content.startswith("# タイトル")


def test_heading_aware_falls_back_to_single_chunk_when_no_headings() -> None:
    body = "見出しのないプレーンな本文です。"
    chunks = chunk_heading_aware(body)
    assert len(chunks) == 1
    assert chunks[0].content == body
    assert chunks[0].section_path == ""


def test_heading_aware_skips_empty_sections_without_index_gaps() -> None:
    body = "# タイトル\n## 空のセクション\n## 本文があるセクション\n中身。"
    chunks = chunk_heading_aware(body)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_fixed_chunking_respects_max_token_budget_and_overlap() -> None:
    body = "\n\n".join(
        f"これは{i}番目の文章です。ERPNaviの設定手順に関する説明が続きます。" for i in range(80)
    )
    max_tokens = 60
    overlap_tokens = 10

    chunks = chunk_fixed(
        body, max_tokens=max_tokens, overlap_tokens=overlap_tokens, strategy_name="test-strategy"
    )

    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.chunk_strategy == "test-strategy" for c in chunks)
    for chunk in chunks:
        assert len(_ENCODING.encode(chunk.content)) <= max_tokens


def test_fixed_chunking_section_path_tracks_heading_position() -> None:
    section_a_text = "alpha " * 60
    section_b_text = "beta " * 60
    body = f"# Title\n\n## Section A\n{section_a_text}\n## Section B\n{section_b_text}"

    chunks = chunk_fixed(body, max_tokens=20, overlap_tokens=5, strategy_name="test-strategy")
    section_paths = [c.section_path for c in chunks]

    assert "Title > Section A" in section_paths
    assert "Title > Section B" in section_paths
    # section_pathはチャンクの開始位置が属する見出しを表す。オーバーラップにより
    # チャンク後半に次セクションの内容が混入することはあるが、開始文字列は必ず
    # section_pathが指す見出し側のテキストである。
    for chunk in chunks:
        if chunk.section_path == "Title > Section A":
            assert not chunk.content.startswith("beta")
        if chunk.section_path == "Title > Section B":
            assert not chunk.content.startswith("alpha")
    last_a_index = max(i for i, p in enumerate(section_paths) if p == "Title > Section A")
    first_b_index = min(i for i, p in enumerate(section_paths) if p == "Title > Section B")
    assert last_a_index < first_b_index


def test_chunk_fixed_rejects_overlap_greater_or_equal_to_max_tokens() -> None:
    with pytest.raises(ValueError, match="overlap_tokens"):
        chunk_fixed("本文です。", max_tokens=10, overlap_tokens=10, strategy_name="test-strategy")


def test_chunk_by_strategy_dispatches_known_strategies() -> None:
    body = "# タイトル\n\n本文です。"

    assert chunk_by_strategy(body, FIXED_512)[0].chunk_strategy == FIXED_512
    assert chunk_by_strategy(body, FIXED_256)[0].chunk_strategy == FIXED_256
    assert chunk_by_strategy(body, HEADING_AWARE)[0].chunk_strategy == HEADING_AWARE


def test_chunk_by_strategy_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="未知のチャンク戦略"):
        chunk_by_strategy("本文", "does-not-exist")
