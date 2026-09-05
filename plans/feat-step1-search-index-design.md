# Step 1: Azure AI Search インデックス設計

関連Issue: #1

## スコープ

Azure AI Search のインデックススキーマをコードとして定義する。実リソースへのデプロイは行わず
（サブスクリプション未準備のため）、スキーマ定義とその単体テストのみを本ステップの範囲とする。

## チャンク分割方針（比較用に複数パターンを設計）

Step 2（インジェストパイプライン）で実データに対して比較評価するため、
インデックス側は分割方針を横断的に記録できる設計にする。

| 方針 | 概要 | 想定用途 |
|---|---|---|
| `fixed_512` | 512トークン固定長、50トークンオーバーラップ | ベースライン |
| `fixed_256` | 256トークン固定長、30トークンオーバーラップ | 短いFAQ向け・粒度比較 |
| `heading_aware` | Markdown見出し単位でのセクション分割 | 手順書のような構造化文書向け |

各チャンクのメタデータに `chunk_strategy` を持たせ、同一ドキュメントセットに対して
複数戦略でインデックスを作り分け、Step 6 の golden_qa 評価で精度差を比較できるようにする。

## メタデータスキーマ

| フィールド | 型 | 属性 | 用途 |
|---|---|---|---|
| `id` | Edm.String | key | `{source_file}_{chunk_index}` のハッシュ |
| `content` | Edm.String | searchable | チャンク本文（BM25対象） |
| `content_vector` | Collection(Edm.Single), dims=3072 | vector search | text-embedding-3-large の埋め込み |
| `title` | Edm.String | searchable, retrievable | ドキュメントタイトル（セマンティック設定のtitleField） |
| `section_path` | Edm.String | retrievable | 見出しパス（例: "3. 初期設定 > 3.2 ユーザー登録"）。回答の引用元表示に使用 |
| `source_type` | Edm.String | filterable, facetable | `manual` / `faq` / `troubleshooting` |
| `source_file` | Edm.String | filterable, retrievable | 元ファイル名 |
| `module_tags` | Collection(Edm.String) | filterable, facetable | 業務モジュール（在庫管理・会計・購買 等） |
| `chunk_index` | Edm.Int32 | retrievable | ドキュメント内の並び順 |
| `chunk_strategy` | Edm.String | filterable | 上記チャンク分割方針の識別子 |
| `last_updated` | Edm.DateTimeOffset | filterable, sortable | ドキュメント最終更新日 |

## ハイブリッド検索設定

- ベクトル検索: HNSWアルゴリズム、`content_vector` フィールド（3072次元、コサイン類似度）
  - 埋め込みはクライアント側（Step 2のインジェストパイプライン、Step 4のクエリ時）で生成するため、
    インデックス側にベクトライザーは設定しない
- セマンティック設定: `titleField=title`, `contentFields=[content]`, `keywordsFields=[module_tags]`
- クエリパターン（Step 4で実装）: BM25キーワード検索 + ベクトル検索 + `queryType=semantic` を
  1リクエストのハイブリッドクエリとして発行する想定

## 実装物

- `src/ingestion/index_schema.py`: 上記スキーマを `azure.search.documents.indexes.models.SearchIndex`
  として構築する関数 `build_search_index(index_name: str) -> SearchIndex`
- `tests/test_index_schema.py`: フィールド構成・型・ベクトル次元数・セマンティック設定を検証する単体テスト
  （Azure資格情報不要、オブジェクト構築のみを検証）
- `src/config.py`: `.env` からAzure OpenAI / AI Search / Cosmos DB の接続設定を読み込むヘルパー
- `scripts/verify_azure_connectivity.py`: 3サービスへの実疎通確認スクリプト
  （エンドポイント・キーの値は一切標準出力しない）

## 動作確認方法

```bash
uv run pytest tests/test_index_schema.py -v
uv run python scripts/verify_azure_connectivity.py  # 要 .env
```

## 実リソースでの検証結果（2026-09-06）

Azureサブスクリプションの準備が整い、実リソースに対して検証済み。

- Azure AI Search: `erp-knowledge-index` を実際に `create_or_update_index` し、11フィールドで作成成功
- Azure OpenAI: 埋め込み生成・チャット応答ともに成功。埋め込みモデルは当初
  `text-embedding-3-small`（1536次元）しかデプロイされておらず、スキーマの3072次元と不一致が
  発覚 → `text-embedding-3-large` を追加デプロイして解消。チャットは `gpt-4o` ではなく
  `gpt-4.1-mini-1` というデプロイ名（クォータ制約により選択肢が限られたため）
- Azure Cosmos DB: `erp-navigator` データベース / `sessions` コンテナの作成に成功
- リージョンは全リソースとも Japan East で統一

**教訓**: `.env` 手動転記時に値へ変数名を二重に含めてしまうミス（`AZURE_OPENAI_ENDPOINT=AZURE_OPENAI_ENDPOINT=https://...`）が発生した。埋め込み/チャット両方が同時に失敗する場合はデプロイ名よりも先にエンドポイント自体を疑うべき、という点は後続ステップでも留意する。
- チャンク分割方針ごとの精度差の実測は Step 6（golden_qa評価）で行う
