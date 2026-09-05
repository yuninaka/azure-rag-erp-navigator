# Step 2: ダミー業務文書のチャンク化・埋め込み生成・インデックス投入パイプライン

関連Issue: #1

## スコープ

架空のERP製品「ERPNavi」を題材にしたダミーの導入マニュアル・FAQ・トラブルシュート事例を作成し、
Step 1で設計した3つのチャンク分割方針（`fixed_512` / `fixed_256` / `heading_aware`）すべてで
チャンク化・埋め込み生成を行い、同一のAzure AI Searchインデックスに投入するパイプラインを実装する。

## ダミーデータセット

`data/dummy_docs/` 配下にYAMLフロントマター付きMarkdownとして作成。

- `manuals/`: 初期設定・ユーザー管理・在庫管理・会計・購買の5モジュール分の導入マニュアル
- `faq/`: モジュール横断のFAQ（1ファイルに複数Q&Aを`##`見出しで格納）
- `troubleshooting/`: 過去の問い合わせ事例集（1ファイルに複数事例を`##`見出しで格納、症状/原因/対処の3段構成）

フロントマターは `title` / `module_tags` / `last_updated` を持つ（`source_type` はディレクトリ名から自動判定）。

## 実装物

- `src/ingestion/document_loader.py`: フロントマター付きMarkdownの読み込み（`SourceDocument`）
- `src/ingestion/chunkers.py`: 3方針のチャンク分割。全方針で見出し階層から `section_path`
  （引用元表示用）を一貫して付与する
  - `fixed_512` / `fixed_256`: tiktoken(`cl100k_base`)によるトークン数固定分割
    （オーバーラップ 50 / 30 トークン）
  - `heading_aware`: Markdown見出し単位（`#`〜`######`すべて）で分割
- `src/ingestion/embed.py`: Azure OpenAI埋め込みのバッチ生成（`embed_texts`、順序保証あり）
- `src/ingestion/ingest_pipeline.py`: チャンク化→埋め込み→Azure AI Search投入のオーケストレーション
  （`chunk_strategy` フィールドで同一インデックス内に3方針のチャンクを共存させる設計。
  Step 6のgolden_qa評価で `$filter=chunk_strategy eq '...'` により方針別の精度を比較する）
- `scripts/ingest_dummy_docs.py`: 全戦略での投入を実行するCLI

## テスト方針

IOを伴わない純粋ロジック（チャンク分割・ドキュメント読み込み・投入ドキュメント整形）は
実際のAzureリソースなしで単体テスト可能な設計にした。Azure呼び出しを行う関数
（`embed_texts` / `run_ingestion`）は呼び出し部分を関数引数として注入できる構造にし、
`embed_texts` はフェイクのAzure OpenAIクライアントでテストしている。`run_ingestion`
自体（配線部分）は単体テスト対象とせず、本ステップでは実リソースに対する実行で動作確認した
（下記「実リソースでの検証結果」参照）。

```bash
uv run pytest tests/test_document_loader.py tests/test_chunkers.py tests/test_embed.py tests/test_ingest_pipeline.py -v
```

## 実リソースでの検証結果（2026-09-06）

```bash
uv run python scripts/ingest_dummy_docs.py
```

- `fixed_512`: 21件 / `fixed_256`: 38件 / `heading_aware`: 40件 投入成功（インデックス合計99件、
  `get_document_count()` で確認）
- キーワード検索（`chunk_strategy eq 'heading_aware'` でフィルタ、クエリ「在庫の発注点アラートが
  届かない」）で、manual・troubleshooting・faqの3種類から関連チャンクが正しくヒットし、
  `section_path` も期待通りの見出しパスを返すことを確認

## 未確認・後続ステップに委ねる事項

- チャンク分割方針ごとの検索精度の定量比較は、golden_qa評価スクリプト（Step 6）で実施する
- ベクトル検索・セマンティックランカーを組み合わせたハイブリッドクエリの実装はStep 4（RAG回答生成ロジック）で行う
