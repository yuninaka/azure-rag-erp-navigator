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


def test_heading_aware_splits_by_heading_with_nested_section_path():
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


def test_fixed_chunking_respects_max_token_budget_and_overlap():
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


def test_chunk_by_strategy_dispatches_known_strategies():
    body = "# タイトル\n\n本文です。"

    assert chunk_by_strategy(body, FIXED_512)[0].chunk_strategy == FIXED_512
    assert chunk_by_strategy(body, FIXED_256)[0].chunk_strategy == FIXED_256
    assert chunk_by_strategy(body, HEADING_AWARE)[0].chunk_strategy == HEADING_AWARE


def test_chunk_by_strategy_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="未知のチャンク戦略"):
        chunk_by_strategy("本文", "does-not-exist")
