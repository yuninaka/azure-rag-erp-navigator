"""Azure OpenAI / AI Search / Cosmos DB への疎通確認スクリプト。

.env に設定した接続情報が実際に機能するかを確認する。エンドポイントやキーの値は
一切標準出力に出さず、成功/失敗と非機微な付随情報（ベクトル次元数、フィールド数等）
のみを表示する。
"""

import sys
from collections.abc import Callable

from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient, PartitionKey
from azure.search.documents.indexes import SearchIndexClient
from openai import AzureOpenAI

from src.config import load_azure_cosmos_config, load_azure_openai_config, load_azure_search_config
from src.ingestion.index_schema import build_search_index


def check_azure_openai() -> None:
    config = load_azure_openai_config()
    client = AzureOpenAI(
        azure_endpoint=config.endpoint,
        api_key=config.api_key,
        api_version=config.api_version,
    )

    sub_failures: list[str] = []

    try:
        embedding = client.embeddings.create(model=config.embedding_deployment, input="接続確認")
        print(f"  埋め込み生成OK: 次元数={len(embedding.data[0].embedding)}")
    except Exception as error:  # noqa: BLE001 - 個別に原因を切り分けて報告する
        print(f"  埋め込み生成 失敗 (deployment={config.embedding_deployment!r}): {error}")
        sub_failures.append("embeddings")

    try:
        chat = client.chat.completions.create(
            model=config.chat_deployment,
            messages=[{"role": "user", "content": "「OK」とだけ返してください。"}],
            max_tokens=5,
        )
        print(f"  チャット応答OK: {chat.choices[0].message.content!r}")
    except Exception as error:  # noqa: BLE001 - 個別に原因を切り分けて報告する
        print(f"  チャット応答 失敗 (deployment={config.chat_deployment!r}): {error}")
        sub_failures.append("chat")

    if sub_failures:
        raise RuntimeError(f"Azure OpenAI呼び出し失敗: {', '.join(sub_failures)}")


def check_azure_search() -> None:
    """接続確認と同時に、コード側のインデックス定義を実リソースへ同期する。

    単なる疎通確認であれば get_index による存在確認で十分だが、本スクリプトは
    「コードのスキーマ定義を単一の真実源とし、実行するたびに実インデックスへ反映する」
    ことを意図した設計にしている（Step 1 実装時からの方針。
    plans/feat-step1-search-index-design.md 参照）。スキーマを変更せずに疎通だけを
    確認したい場合は、このスクリプトではなく get_index を直接呼び出すこと。
    """
    config = load_azure_search_config()
    client = SearchIndexClient(config.endpoint, AzureKeyCredential(config.api_key))

    index = build_search_index(config.index_name)
    client.create_or_update_index(index)
    created = client.get_index(config.index_name)
    print(f"  インデックス作成/更新OK: name={created.name}, フィールド数={len(created.fields)}")


def check_cosmos_db() -> None:
    config = load_azure_cosmos_config()
    client = CosmosClient(config.endpoint, credential=config.key)

    database = client.create_database_if_not_exists(id=config.database_name)
    container = database.create_container_if_not_exists(
        id=config.sessions_container,
        partition_key=PartitionKey(path="/sessionId"),
    )
    print(f"  データベース/コンテナ作成OK: db={database.id}, container={container.id}")


CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("Azure OpenAI", check_azure_openai),
    ("Azure AI Search", check_azure_search),
    ("Azure Cosmos DB", check_cosmos_db),
]


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        print(f"[{name}] 確認中...")
        try:
            check()
        except Exception as error:  # noqa: BLE001 - 診断スクリプトのため全サービスを試す
            print(f"  失敗: {type(error).__name__}: {error}")
            failures.append(name)

    print()
    if failures:
        print(f"NG: {', '.join(failures)} で疎通確認に失敗しました。")
        return 1
    print("OK: 全サービスへの疎通確認が完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
