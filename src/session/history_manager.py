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

**既知の非対称性（意図した設計ではない）**: Cosmos DBのTTLは、ドキュメントが更新される
たびに `_ts`（最終更新時刻）を起点に再カウントされる。`append_turn` はターンのたびに
セッションメタデータを `patch_item` で更新するため、会話が続く限りメタデータのTTLは
実質的にリセットされ続け「最終アクティブ日時 + session_ttl_seconds」まで消えない。一方
ターンドキュメントは作成後に更新されないため、作成から確実に `session_ttl_seconds` 後に
失効する。そのため、`session_ttl_seconds`（デフォルト30日）を超えて続く長期セッションでは、
最初期のターンだけが会話継続中に消え、`turn_count` は実際に残っているターン数より
大きい値のまま、という状態が起こり得る（＝「セッションメタデータだけ残り、
一部のターン履歴が消える」）。

代替案（未実装。今回は現状の挙動を許容し、方針の提示のみ行う）:
1. セッション作成時刻を起点にした固定の絶対期限を全ドキュメントに一律で設定する
   （実装は単純だが、アクティブな会話でもセッション自体が丸ごと消えてしまう）
2. Cosmos DBのネイティブTTLに頼らず、`last_active_at` を見て期限切れセッションの
   全ドキュメントを削除する定期ジョブ（Azure Functions等）を別途設ける
   （パーティション単位の一括失効を正しく表現できるが、運用コンポーネントが増える）
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TypedDict, cast

from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError

logger = logging.getLogger(__name__)

_SESSION_META_TYPE = "session_meta"
_TURN_TYPE = "turn"
DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30日


class SessionMeta(TypedDict):
    id: str
    sessionId: str
    type: str
    created_at: str
    last_active_at: str
    turn_count: int
    ttl: int


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
    ) -> None:
        self._container = container
        self._session_ttl_seconds = session_ttl_seconds

    def _read_session_meta(self, session_id: str) -> SessionMeta:
        # Cosmos DBはスキーマレスなドキュメントストアのため、SDKの戻り値は
        # 動的な Mapping になる。読み書き双方を本クラスが管理しており、
        # 実際のドキュメント形状は SessionMeta と一致することが保証できるため、
        # ここでのみ cast を使う（isinstanceで1フィールドずつ検証するのは過剰）。
        raw = self._container.read_item(item=session_id, partition_key=session_id)
        return cast(SessionMeta, dict(raw))

    def start_session(self, session_id: str) -> SessionMeta:
        """セッションメタデータを取得する。なければ新規作成する（冪等）。

        同一 session_id への初回アクセスがほぼ同時に複数来た場合、両方が
        read_item で「存在しない」と判定し、両方が create_item を呼ぶ競合が
        起こり得る。後勝ちの create_item は 409 Conflict になるため、それを
        「他のリクエストが先に作成した」正常系とみなし、作成済みのドキュメントを
        読み直して返す。
        """
        try:
            return self._read_session_meta(session_id)
        except CosmosResourceNotFoundError:
            pass
        now = _now_iso()
        meta: SessionMeta = {
            "id": session_id,
            "sessionId": session_id,
            "type": _SESSION_META_TYPE,
            "created_at": now,
            "last_active_at": now,
            "turn_count": 0,
            "ttl": self._session_ttl_seconds,
        }
        try:
            self._container.create_item(dict(meta))
        except CosmosResourceExistsError:
            return self._read_session_meta(session_id)
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
        try:
            self._container.patch_item(
                item=session_id,
                partition_key=session_id,
                patch_operations=[
                    {"op": "set", "path": "/turn_count", "value": turn_index + 1},
                    {"op": "set", "path": "/last_active_at", "value": turn.created_at},
                ],
            )
        except Exception:
            # ターン本体はcreate_item済みだが turn_count の更新に失敗した状態。
            # 次回append_turnが同じturn_indexを採番し409 Conflictになりうるため、
            # 調査できるよう警告ログを残した上で例外は呼び出し元に伝播させる
            # （リトライ等は行わない。詳細はplans/feat-step3-cosmos-session-management.md参照）。
            logger.warning(
                "turn_countの更新に失敗しました。turn_index=%d は保存済みですが、"
                "次回append_turnで同じturn_indexが再利用され409 Conflictになる可能性があります"
                "(session_id=%s)",
                turn_index,
                session_id,
                exc_info=True,
            )
            raise
        return turn

    def get_history(self, session_id: str, *, max_turns: int | None = None) -> list[Turn]:
        """セッションの全ターンをターン番号順に返す。`max_turns` 指定時は直近N件のみ。"""
        items = list(
            self._container.query_items(
                query=(
                    "SELECT * FROM c WHERE c.sessionId=@sid AND c.type=@type "
                    "ORDER BY c.turn_index ASC"
                ),
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
