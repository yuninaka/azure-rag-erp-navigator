"""Cosmos DB の会話履歴コンテナへの接続。"""

from azure.cosmos import ContainerProxy, CosmosClient, PartitionKey

from src.config import AzureCosmosConfig

# セッションデータに寿命を持たせられるよう defaultTtl=-1 で作成する。
# -1 は「コンテナ全体には既定の有効期限を設けないが、アイテム個別の `ttl` フィールドで
# 明示的に指定されたものだけを期限切れにする」設定（Cosmos DBの仕様）。
_SESSIONS_DEFAULT_TTL = -1


def get_sessions_container(config: AzureCosmosConfig) -> ContainerProxy:
    """`.env` の設定からCosmos DBのセッション用コンテナを取得する（なければ作成）。"""
    client = CosmosClient(config.endpoint, credential=config.key)
    database = client.create_database_if_not_exists(id=config.database_name)
    return database.create_container_if_not_exists(
        id=config.sessions_container,
        partition_key=PartitionKey(path="/sessionId"),
        default_ttl=_SESSIONS_DEFAULT_TTL,
    )
