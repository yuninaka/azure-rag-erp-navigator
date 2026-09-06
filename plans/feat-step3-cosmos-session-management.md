# Step 3: Cosmos DBでの会話履歴・セッション管理

関連Issue: #1

## スコープ

マルチターン対話を想定した会話履歴・セッション管理をAzure Cosmos DB（NoSQL API）上に実装する。
Step 4（RAG回答生成ロジック）から利用できる形で、履歴の保存・取得・チャットAPI形式への変換までを提供する。

## データモデル

コンテナ `sessions`（パーティションキー `/sessionId`、Step 1検証時に作成済み）に、
以下2種類のドキュメントを同一パーティション内に共存させる設計とした。

| 種別 | id | 用途 |
|---|---|---|
| セッションメタデータ | `{sessionId}` | 作成日時・最終アクティブ日時・累積ターン数 |
| ターン | `{sessionId}-{turn_index:04d}` | 1往復（質問・回答・引用元）を1ドキュメントに格納 |

**採番方式の判断**: ターン追加のたびに `COUNT(1)` クエリで既存件数を数え直す方式ではなく、
セッションメタデータの `turn_count` を点読み（1 RU程度の安価な操作）して次のターン番号とし、
ターン作成後に `patch_item` で `turn_count` をインクリメントする方式にした。単一パーティション内の
点読み・patchはクエリよりも安価かつ低レイテンシなため。

**TTLによる自動失効**: コンテナを `defaultTtl=-1` で作成（Step1検証時に作成済みの既存コンテナは
本ステップで `replace_container` により一度だけ更新した）。これにより、コンテナ全体には既定の
有効期限を設けず、各ドキュメントの `ttl` フィールド（本実装ではデフォルト30日 `DEFAULT_SESSION_TTL_SECONDS`）
で個別に有効期限を指定できる。放置された古いセッションデータを手動削除なしで自動失効させ、
Cosmos DBのストレージコストを抑える運用上の狙い。

## 実装物

- `src/session/cosmos_client.py`: `.env` の設定からセッション用コンテナを取得（`get_sessions_container`）
- `src/session/history_manager.py`: `SessionHistoryManager`
  - `start_session`: セッションメタデータの取得、なければ冪等に新規作成
  - `append_turn`: 1往復を履歴に追加（セッション未作成時は自動作成）
  - `get_history`: ターン番号順に履歴取得（`max_turns`で直近N件に制限可）
  - `build_chat_messages`: 履歴をAzure OpenAIのchatメッセージ形式（role/content）に変換
    （Step 4のRAG回答生成にそのまま渡せる設計）
- `scripts/measure_session_latency.py`: レイテンシ実測スクリプト

## テスト方針

`ContainerProxy` の代わりに `tests/fakes/fake_cosmos_container.py` のインメモリフェイクを使い、
実Cosmos DBなしで `SessionHistoryManager` の全ロジックを単体テストしている。

```bash
uv run pytest tests/test_history_manager.py -v
```

## 実リソースでの検証結果（2026-09-06）

```bash
uv run python scripts/measure_session_latency.py
```

- `append_turn` 1回目（セッション新規作成込み: メタ点読みmiss→メタ作成→ターン作成→メタpatch、
  計3ラウンドトリップ）: 約280ms
- `append_turn` 2回目以降（メタ点読みhit→ターン作成→メタpatch、計3ラウンドトリップ）:
  平均64.5ms、最大85.2ms — ターン数が増えても悪化しない（各操作が単一ドキュメント点操作のため）
- `get_history`（10件取得、単一パーティションクエリ）: 88.1ms

**考察メモ（Zenn記事用）**: 初回のみ約280msと有意に遅いのは、セッションメタデータの
存在確認（点読みmiss→404）と新規作成が追加で発生するため。2回目以降は3ラウンドトリップでも
60〜90ms程度に収まっており、チャットUIの応答時間（Azure OpenAIの生成に数百ms〜数秒かかる）
と比べると体感への影響は小さいと考えられる。ただし本実装は `create_item` → `patch_item` を
直列に実行しており、非同期化・バッチ化（Cosmos DBのTransactional Batch）で追加の高速化余地がある。

## 未確認・後続ステップに委ねる事項

- `build_chat_messages` の実際の消費（Azure OpenAIへの受け渡し）はStep 4で実装する
- **既知のリスク（未対応）**: `append_turn` はターン本体の `create_item` →
  メタデータの `turn_count` の `patch_item` を直列実行しており、Transactional Batchによる
  一括化は行っていない。後者の `patch_item` が（ネットワーク瞬断・スロットリング等で）
  失敗すると、ターンドキュメントは保存済みなのに `turn_count` が更新されず、
  次回の `append_turn` が同じ `turn_index` を採番して `create_item` が409 Conflictで
  失敗する不整合が起こり得る。小規模な検証用途では、この複雑さ（Transactional Batch導入）に
  見合わないと判断し、本ステップでは対応を見送った。本番運用を想定する場合は、
  Transactional Batchでの原子的な実行、またはpatch失敗時のリトライ＋turn_index重複検知の
  導入を検討すべき
