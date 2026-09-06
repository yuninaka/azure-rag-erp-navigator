"""チャットUI表示用のフォーマット関数（Streamlit非依存の純粋ロジック）。"""

from src.session.history_manager import Citation


def format_citations_markdown(citations: list[Citation]) -> str:
    """引用元リストを、Streamlitのst.markdownにそのまま渡せる箇条書きに変換する。"""
    if not citations:
        return ""
    lines = [
        f"- [{i}] {c.section_path} ({c.source_file})" for i, c in enumerate(citations, start=1)
    ]
    return "\n".join(lines)
