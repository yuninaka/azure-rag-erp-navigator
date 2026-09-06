"""Azure OpenAIを使ったRAG回答生成（検索・履歴・引用元提示の統合）。"""

from dataclasses import dataclass
from typing import cast

from openai.types.chat import ChatCompletionMessageParam

from src.ingestion.embed import embed_texts
from src.rag.citations import build_citations
from src.rag.dependencies import RagDependencies
from src.rag.prompt_templates import SYSTEM_PROMPT, build_user_message
from src.rag.search_client import DEFAULT_CHUNK_STRATEGY, DEFAULT_TOP_K, hybrid_search
from src.session.history_manager import Citation

DEFAULT_HISTORY_TURNS = 5
# コンテンツフィルタ作動時等、Azure OpenAIがcontent=Noneを返すケースのフォールバック文言。
# 履歴には「その質問には回答できなかった」という事実として残す（保存自体はスキップしない）。
FALLBACK_ANSWER = "回答を生成できませんでした。担当部署にお問い合わせください。"


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[Citation]


def generate_answer(
    *,
    query: str,
    session_id: str,
    deps: RagDependencies,
    top_k: int = DEFAULT_TOP_K,
    chunk_strategy: str = DEFAULT_CHUNK_STRATEGY,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> RagAnswer:
    """質問に対しハイブリッド検索→履歴考慮→回答生成を行い、履歴に保存して返す。"""
    query_vector = embed_texts(deps.openai_client, deps.embedding_deployment, [query])[0]
    hits = hybrid_search(
        deps.search_client, query, query_vector, top=top_k, chunk_strategy=chunk_strategy
    )
    citations = build_citations(hits)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *deps.history_manager.build_chat_messages(session_id, max_turns=history_turns),
        {"role": "user", "content": build_user_message(query, hits)},
    ]
    response = deps.openai_client.chat.completions.create(
        model=deps.chat_deployment,
        # roleは実行時には必ず"system"/"user"/"assistant"のリテラル値になるが、
        # SessionHistoryManager.build_chat_messagesの戻り値型は汎用的な
        # list[dict[str, str]]であり、OpenAI SDKが要求するリテラル型のUnionとは
        # 静的には一致しないため、このAPI境界でのみcastする。
        messages=cast(list[ChatCompletionMessageParam], messages),
    )
    answer = response.choices[0].message.content or FALLBACK_ANSWER

    deps.history_manager.append_turn(session_id, query, answer, citations)
    return RagAnswer(answer=answer, citations=citations)
