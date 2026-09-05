"""Azure OpenAI を使ったテキスト埋め込み生成。"""

from openai import AzureOpenAI

_DEFAULT_BATCH_SIZE = 16


def embed_texts(
    client: AzureOpenAI,
    deployment: str,
    texts: list[str],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> list[list[float]]:
    """`texts` と同じ順序で埋め込みベクトルのリストを返す。"""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=deployment, input=batch)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)
    return vectors
