"""環境変数から Azure サービスの接続設定を読み込む。"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"必須環境変数が未設定です: {name}（.env を確認してください）")
    return value


@dataclass(frozen=True)
class AzureOpenAIConfig:
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str
    embedding_deployment: str


@dataclass(frozen=True)
class AzureSearchConfig:
    endpoint: str
    api_key: str
    index_name: str


@dataclass(frozen=True)
class AzureCosmosConfig:
    endpoint: str
    key: str
    database_name: str
    sessions_container: str


def load_azure_openai_config() -> AzureOpenAIConfig:
    return AzureOpenAIConfig(
        endpoint=_require_env("AZURE_OPENAI_ENDPOINT"),
        api_key=_require_env("AZURE_OPENAI_API_KEY"),
        api_version=_require_env("AZURE_OPENAI_API_VERSION"),
        chat_deployment=_require_env("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        embedding_deployment=_require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )


def load_azure_search_config() -> AzureSearchConfig:
    return AzureSearchConfig(
        endpoint=_require_env("AZURE_SEARCH_ENDPOINT"),
        api_key=_require_env("AZURE_SEARCH_API_KEY"),
        index_name=_require_env("AZURE_SEARCH_INDEX_NAME"),
    )


def load_azure_cosmos_config() -> AzureCosmosConfig:
    return AzureCosmosConfig(
        endpoint=_require_env("AZURE_COSMOS_ENDPOINT"),
        key=_require_env("AZURE_COSMOS_KEY"),
        database_name=_require_env("AZURE_COSMOS_DATABASE_NAME"),
        sessions_container=_require_env("AZURE_COSMOS_SESSIONS_CONTAINER"),
    )
