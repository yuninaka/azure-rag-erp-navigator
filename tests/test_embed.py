from dataclasses import dataclass

from src.ingestion.embed import embed_texts


@dataclass
class _FakeEmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem]


class _FakeEmbeddingsResource:
    def __init__(self):
        self.calls: list[list[str]] = []

    def create(self, *, model: str, input: list[str]):
        self.calls.append(list(input))
        items = [
            _FakeEmbeddingItem(index=i, embedding=[float(len(text)), float(i)])
            for i, text in enumerate(input)
        ]
        return _FakeEmbeddingResponse(data=list(reversed(items)))  # 順序が乱れて返る想定


class _FakeAzureOpenAIClient:
    def __init__(self):
        self.embeddings = _FakeEmbeddingsResource()


def test_embed_texts_batches_requests_and_preserves_input_order():
    client = _FakeAzureOpenAIClient()
    texts = [f"text-{i}" for i in range(5)]

    vectors = embed_texts(client, "test-deployment", texts, batch_size=2)

    text_length = float(len("text-0"))
    assert vectors == [
        [text_length, 0.0],
        [text_length, 1.0],
        [text_length, 0.0],
        [text_length, 1.0],
        [text_length, 0.0],
    ]
    assert len(client.embeddings.calls) == 3  # 5件をbatch_size=2で処理 -> 2,2,1
    assert client.embeddings.calls == [["text-0", "text-1"], ["text-2", "text-3"], ["text-4"]]
