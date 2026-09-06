"""検索結果から回答の引用元情報を構築する。"""

from src.rag.search_client import SearchHit
from src.session.history_manager import Citation


def build_citations(hits: list[SearchHit]) -> list[Citation]:
    return [
        Citation(title=hit.title, section_path=hit.section_path, source_file=hit.source_file)
        for hit in hits
    ]
