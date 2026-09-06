from types import SimpleNamespace

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
    def create(self, *, model, input):
        data = [SimpleNamespace(index=i, embedding=[0.0]) for i in range(len(input))]
        return SimpleNamespace(data=data)


class _FakeChatCompletionsResource:
    def __init__(self, content: str | None):
        self._content = content

    def create(self, **kwargs):
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeAzureOpenAIClient:
    def __init__(self, chat_content: str | None):
        self.embeddings = _FakeEmbeddingsResource()
        self.chat = SimpleNamespace(completions=_FakeChatCompletionsResource(chat_content))


class _FakeSearchClient:
    def __init__(self, results: list[dict]):
        self._results = results

    def search(self, **kwargs):
        return self._results


def _history_manager() -> SessionHistoryManager:
    return SessionHistoryManager(FakeCosmosContainer(), session_ttl_seconds=3600)


def test_generate_answer_returns_answer_and_citations_on_success():
    history_manager = _history_manager()

    result = generate_answer(
        query="初期設定はどこから始めますか？",
        session_id="session-1",
        openai_client=_FakeAzureOpenAIClient(chat_content="テナント作成から始めてください。[1]"),
        embedding_deployment="embed-deployment",
        chat_deployment="chat-deployment",
        search_client=_FakeSearchClient([RAW_HIT]),
        history_manager=history_manager,
    )

    assert result.answer == "テナント作成から始めてください。[1]"
    assert len(result.citations) == 1
    assert result.citations[0].title == "初期設定ガイド"
    saved = history_manager.get_history("session-1")
    assert saved[0].assistant_message == "テナント作成から始めてください。[1]"


def test_generate_answer_falls_back_and_still_saves_history_when_content_is_none():
    history_manager = _history_manager()

    result = generate_answer(
        query="質問",
        session_id="session-1",
        openai_client=_FakeAzureOpenAIClient(chat_content=None),
        embedding_deployment="embed-deployment",
        chat_deployment="chat-deployment",
        search_client=_FakeSearchClient([]),
        history_manager=history_manager,
    )

    assert result.answer == FALLBACK_ANSWER
    saved = history_manager.get_history("session-1")
    assert len(saved) == 1
    assert saved[0].assistant_message == FALLBACK_ANSWER
