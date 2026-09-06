"""Azure OpenAIを使ったRAG回答生成（検索・履歴・引用元提示の統合）。"""

from dataclasses import dataclass

from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.ingestion.embed import embed_texts
from src.rag.citations import build_citations
from src.rag.prompt_templates import SYSTEM_PROMPT, build_user_message
from src.rag.search_client import DEFAULT_CHUNK_STRATEGY, DEFAULT_TOP_K, hybrid_search
from src.session.history_manager import Citation, SessionHistoryManager

DEFAULT_HISTORY_TURNS = 5


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[Citation]


def generate_answer(
    *,
    query: str,
    session_id: str,
    openai_client: AzureOpenAI,
    embedding_deployment: str,
    chat_deployment: str,
    search_client: SearchClient,
    history_manager: SessionHistoryManager,
    top_k: int = DEFAULT_TOP_K,
    chunk_strategy: str = DEFAULT_CHUNK_STRATEGY,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> RagAnswer:
    """質問に対しハイブリッド検索→履歴考慮→回答生成を行い、履歴に保存して返す。"""
    query_vector = embed_texts(openai_client, embedding_deployment, [query])[0]
    hits = hybrid_search(
        search_client, query, query_vector, top=top_k, chunk_strategy=chunk_strategy
    )
    citations = build_citations(hits)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history_manager.build_chat_messages(session_id, max_turns=history_turns),
        {"role": "user", "content": build_user_message(query, hits)},
    ]
    response = openai_client.chat.completions.create(model=chat_deployment, messages=messages)
    answer = response.choices[0].message.content

    history_manager.append_turn(session_id, query, answer, citations)
    return RagAnswer(answer=answer, citations=citations)
