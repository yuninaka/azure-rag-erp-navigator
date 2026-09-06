"""チャンク分割方針の実装（fixed_512 / fixed_256 / heading_aware）。

方針の比較検証のため、どの戦略でもチャンクの引用元表示に使う `section_path`
（見出しパス）を一貫した方法で付与する。詳細は
plans/feat-step1-search-index-design.md を参照。
"""

import re
from dataclasses import dataclass
from itertools import pairwise

import tiktoken

FIXED_512 = "fixed_512"
FIXED_256 = "fixed_256"
HEADING_AWARE = "heading_aware"
ALL_STRATEGIES = [FIXED_512, FIXED_256, HEADING_AWARE]

_ENCODING = tiktoken.get_encoding("cl100k_base")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    content: str
    section_path: str
    chunk_index: int
    chunk_strategy: str


def _extract_headings(body: str) -> list[tuple[int, int, str]]:
    return [
        (match.start(), len(match.group(1)), match.group(2).strip())
        for match in _HEADING_PATTERN.finditer(body)
    ]


def _section_path_at(offset: int, headings: list[tuple[int, int, str]]) -> str:
    stack: dict[int, str] = {}
    for heading_offset, level, text in headings:
        if heading_offset > offset:
            break
        stack = {lvl: txt for lvl, txt in stack.items() if lvl < level}
        stack[level] = text
    return " > ".join(stack[level] for level in sorted(stack))


def _fixed_token_windows(tokens: list[int], max_tokens: int, step: int) -> list[tuple[int, str]]:
    windows = []
    start = 0
    while start < len(tokens):
        text = _ENCODING.decode(tokens[start : start + max_tokens]).strip()
        if text:
            windows.append((start, text))
        if start + max_tokens >= len(tokens):
            break
        start += step
    return windows


def chunk_fixed(
    body: str, *, max_tokens: int, overlap_tokens: int, strategy_name: str
) -> list[Chunk]:
    """トークン数固定・オーバーラップありでチャンク分割する。"""
    if overlap_tokens >= max_tokens:
        raise ValueError(
            f"overlap_tokens({overlap_tokens})はmax_tokens({max_tokens})未満である必要があります"
        )
    headings = _extract_headings(body)
    tokens = _ENCODING.encode(body)
    chunks: list[Chunk] = []
    for start, text in _fixed_token_windows(tokens, max_tokens, max_tokens - overlap_tokens):
        char_offset = len(_ENCODING.decode(tokens[:start]))
        chunks.append(
            Chunk(
                content=text,
                section_path=_section_path_at(char_offset, headings),
                chunk_index=len(chunks),
                chunk_strategy=strategy_name,
            )
        )
    return chunks


def chunk_heading_aware(body: str, *, strategy_name: str = HEADING_AWARE) -> list[Chunk]:
    """Markdownの見出し単位でチャンク分割する。見出しが1つもない本文は全体を1チャンクとする。"""
    headings = _extract_headings(body)
    if not headings:
        return [
            Chunk(
                content=body.strip(), section_path="", chunk_index=0, chunk_strategy=strategy_name
            )
        ]
    boundaries = [offset for offset, _, _ in headings] + [len(body)]
    chunks: list[Chunk] = []
    for start, end in pairwise(boundaries):
        content = body[start:end].strip()
        if not content:
            continue
        chunks.append(
            Chunk(
                content=content,
                section_path=_section_path_at(start, headings),
                chunk_index=len(chunks),
                chunk_strategy=strategy_name,
            )
        )
    return chunks


def chunk_by_strategy(body: str, strategy: str) -> list[Chunk]:
    if strategy == FIXED_512:
        return chunk_fixed(body, max_tokens=512, overlap_tokens=50, strategy_name=FIXED_512)
    if strategy == FIXED_256:
        return chunk_fixed(body, max_tokens=256, overlap_tokens=30, strategy_name=FIXED_256)
    if strategy == HEADING_AWARE:
        return chunk_heading_aware(body, strategy_name=HEADING_AWARE)
    raise ValueError(f"未知のチャンク戦略です: {strategy}")
