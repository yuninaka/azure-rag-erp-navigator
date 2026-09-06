"""Cosmos DB を使った会話履歴・セッション管理（マルチターン対話用）。

1セッション = 1つの `sessionId` パーティション。ドキュメントは以下の2種類を
同一コンテナ・同一パーティションに共存させる設計とする。

- セッションメタデータ（`id == sessionId`、1セッションにつき1件）: 作成日時・
  最終アクティブ日時・ターン数を保持する。`turn_count` を読むだけで次のターン番号が
  分かるため、ターン追加のたびに全履歴をカウントし直すクエリを避けられる。
- ターン（`id == "{sessionId}-{turn_index:04d}"`）: 1往復（ユーザー発言・
  アシスタント応答・引用元）を1ドキュメントとして保持する。

どちらも `ttl` フィールドを持たせ、`src/session/cosmos_client.py` 側の
`defaultTtl=-1` 設定と組み合わせて、セッションデータを一定期間後に自動失効させる。
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

_SESSION_META_TYPE = "session_meta"
_TURN_TYPE = "turn"
DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30日


@dataclass(frozen=True)
class Citation:
    title: str
    section_path: str
    source_file: str


@dataclass(frozen=True)
class Turn:
    session_id: str
    turn_index: int
    user_message: str
    assistant_message: str
    citations: list[Citation] = field(default_factory=list)
    created_at: str = ""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _turn_document_id(session_id: str, turn_index: int) -> str:
    return f"{session_id}-{turn_index:04d}"


class SessionHistoryManager:
    def __init__(
        self, container: ContainerProxy, *, session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    ):
        self._container = container
        self._session_ttl_seconds = session_ttl_seconds

    def start_session(self, session_id: str) -> dict:
        """セッションメタデータを取得する。なければ新規作成する（冪等）。"""
        try:
            return dict(self._container.read_item(item=session_id, partition_key=session_id))
        except CosmosResourceNotFoundError:
            pass
        now = _now_iso()
        meta = {
            "id": session_id,
            "sessionId": session_id,
            "type": _SESSION_META_TYPE,
            "created_at": now,
            "last_active_at": now,
            "turn_count": 0,
            "ttl": self._session_ttl_seconds,
        }
        self._container.create_item(meta)
        return meta

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        citations: list[Citation] | None = None,
    ) -> Turn:
        """1往復を履歴に追加する。セッションが未作成なら自動的に作成する。"""
        meta = self.start_session(session_id)
        turn_index = meta["turn_count"]
        turn = Turn(
            session_id=session_id,
            turn_index=turn_index,
            user_message=user_message,
            assistant_message=assistant_message,
            citations=citations or [],
            created_at=_now_iso(),
        )
        self._container.create_item(
            {
                "id": _turn_document_id(session_id, turn_index),
                "sessionId": session_id,
                "type": _TURN_TYPE,
                "turn_index": turn.turn_index,
                "user_message": turn.user_message,
                "assistant_message": turn.assistant_message,
                "citations": [asdict(c) for c in turn.citations],
                "created_at": turn.created_at,
                "ttl": self._session_ttl_seconds,
            }
        )
        self._container.patch_item(
            item=session_id,
            partition_key=session_id,
            patch_operations=[
                {"op": "set", "path": "/turn_count", "value": turn_index + 1},
                {"op": "set", "path": "/last_active_at", "value": turn.created_at},
            ],
        )
        return turn

    def get_history(self, session_id: str, *, max_turns: int | None = None) -> list[Turn]:
        """セッションの全ターンをターン番号順に返す。`max_turns` 指定時は直近N件のみ。"""
        items = list(
            self._container.query_items(
                query="SELECT * FROM c WHERE c.sessionId=@sid AND c.type=@type ORDER BY c.turn_index ASC",
                parameters=[
                    {"name": "@sid", "value": session_id},
                    {"name": "@type", "value": _TURN_TYPE},
                ],
                partition_key=session_id,
            )
        )
        turns = [
            Turn(
                session_id=session_id,
                turn_index=item["turn_index"],
                user_message=item["user_message"],
                assistant_message=item["assistant_message"],
                citations=[Citation(**c) for c in item["citations"]],
                created_at=item["created_at"],
            )
            for item in items
        ]
        return turns[-max_turns:] if max_turns is not None else turns

    def build_chat_messages(self, session_id: str, *, max_turns: int = 5) -> list[dict[str, str]]:
        """直近の履歴をAzure OpenAIのchatメッセージ形式（role/content）に変換する。"""
        messages = []
        for turn in self.get_history(session_id, max_turns=max_turns):
            messages.append({"role": "user", "content": turn.user_message})
            messages.append({"role": "assistant", "content": turn.assistant_message})
        return messages
