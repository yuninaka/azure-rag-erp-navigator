from types import SimpleNamespace
from typing import Any

from src.rag.dependencies import RagDependencies
from src.rag.generator import FALLBACK_ANSWER, generate_answer
from src.session.history_manager import SessionHistoryManager
from tests.fakes.fake_cosmos_container import FakeCosmosContainer

RAW_HIT = {
    "content": "テナント作成の手順です。",
    "title": "初期設定ガイド",
    "section_path": "初期設定ガイド > テナントの作成",
    "source_file": "01_initial_setup.md",
    "@search.score": 1.5,
}


class _FakeEmbeddingsResource:
    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        data = [SimpleNamespace(index=i, embedding=[0.0]) for i in range(len(input))]
        return SimpleNamespace(data=data)


class _FakeChatCompletionsResource:
    def __init__(self, content: str | None) -> None:
        self._content = content

    def create(self, **kwargs: object) -> SimpleNamespace:
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeAzureOpenAIClient:
    def __init__(self, chat_content: str | None) -> None:
        self.embeddings = _FakeEmbeddingsResource()
        self.chat = SimpleNamespace(completions=_FakeChatCompletionsResource(chat_content))


class _FakeSearchClient:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self._results = results

    def search(self, **kwargs: object) -> list[dict[str, Any]]:
        return self._results


def _history_manager() -> SessionHistoryManager:
    return SessionHistoryManager(FakeCosmosContainer(), session_ttl_seconds=3600)


def _deps(
    *,
    chat_content: str | None,
    search_results: list[dict[str, Any]],
    history_manager: SessionHistoryManager,
) -> RagDependencies:
    return RagDependencies(
        # 実SDK型を要求するdataclassフィールドに、必要なメソッドのみを実装した
        # duck-typingフェイクを渡している（実Azure接続なしでテストするため）。
        openai_client=_FakeAzureOpenAIClient(chat_content=chat_content),  # type: ignore[arg-type]
        embedding_deployment="embed-deployment",
        chat_deployment="chat-deployment",
        search_client=_FakeSearchClient(search_results),  # type: ignore[arg-type]
        history_manager=history_manager,
    )


def test_generate_answer_returns_answer_and_citations_on_success() -> None:
    history_manager = _history_manager()
    deps = _deps(
        chat_content="テナント作成から始めてください。[1]",
        search_results=[RAW_HIT],
        history_manager=history_manager,
    )

    result = generate_answer(
        query="初期設定はどこから始めますか？", session_id="session-1", deps=deps
    )

    assert result.answer == "テナント作成から始めてください。[1]"
    assert len(result.citations) == 1
    assert result.citations[0].title == "初期設定ガイド"
    saved = history_manager.get_history("session-1")
    assert saved[0].assistant_message == "テナント作成から始めてください。[1]"


def test_generate_answer_falls_back_and_still_saves_history_when_content_is_none() -> None:
    history_manager = _history_manager()
    deps = _deps(chat_content=None, search_results=[], history_manager=history_manager)

    result = generate_answer(query="質問", session_id="session-1", deps=deps)

    assert result.answer == FALLBACK_ANSWER
    saved = history_manager.get_history("session-1")
    assert len(saved) == 1
    assert saved[0].assistant_message == FALLBACK_ANSWER
