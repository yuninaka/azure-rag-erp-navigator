# azure-rag-erp-navigator

Azure OpenAI Service + Azure AI Search + Cosmos DB を用いた RAG ハンズオン検証プロジェクト。
ERP／基幹システムの導入マニュアル・FAQ・問い合わせ履歴を模したダミーデータセットに対し、
自然言語で質問すると導入・設定手順をナビゲートするチャットボットを構築し、精度・運用面を検証する。

過去の Neo4j × LangChain Agent によるグラフ×ベクトルのハイブリッド RAG 検証（golden_qa 平均 1.00）に対する、
Azure ネイティブスタックでの比較検証記事のための実装。

## アーキテクチャ

```mermaid
flowchart TB
    subgraph Client["利用者"]
        User["業務担当者"]
    end

    subgraph UI["Streamlit UI (App Service)"]
        Chat["チャット画面<br/>質問入力・履歴表示・引用元表示"]
    end

    subgraph AOAI["Azure OpenAI Service"]
        Embed["text-embedding-3-large<br/>(クエリ埋め込み)"]
        GPT["GPT-4o<br/>(回答生成)"]
    end

    subgraph Search["Azure AI Search"]
        Index["ERPナレッジインデックス<br/>ベクトル + キーワード + セマンティックランカー"]
    end

    subgraph Cosmos["Azure Cosmos DB (NoSQL API)"]
        Sessions["sessions コンテナ<br/>会話履歴・マルチターン文脈"]
    end

    subgraph Monitor["監視"]
        AI["Application Insights"]
    end

    User --> Chat
    Chat -->|質問| Embed
    Embed -->|埋め込みベクトル| Index
    Chat -->|会話履歴取得/保存| Sessions
    Index -->|関連チャンク top-k| Chat
    Chat -->|質問+履歴+検索結果| GPT
    GPT -->|回答+引用| Chat
    Chat -.->|テレメトリ| AI
    GPT -.->|テレメトリ| AI
    Index -.->|テレメトリ| AI

    subgraph Ingest["インジェストパイプライン (オフライン/バッチ)"]
        Docs["ダミー業務文書<br/>マニュアル・FAQ・問い合わせ履歴"]
        Chunk["チャンク分割<br/>(複数方針を比較)"]
        EmbedBatch["埋め込み生成"]
    end

    Docs --> Chunk --> EmbedBatch -->|投入| Index
```

## ディレクトリ構成

```
azure-rag-erp-navigator/
├── infra/bicep/        # IaC (Azure OpenAI / AI Search / Cosmos DB / App Service)
├── data/dummy_docs/    # ダミー業務マニュアル・FAQ・トラブルシュート事例
├── src/
│   ├── ingestion/       # チャンク分割・埋め込み生成・インデックス投入
│   ├── rag/             # ハイブリッド検索・回答生成・引用元整形
│   ├── session/         # Cosmos DB による会話履歴・セッション管理
│   └── app/             # Streamlit チャットUI
├── eval/                # golden_qa 評価スクリプト（キーワード網羅率 / RAGAS）
├── tests/               # pytest
├── .github/workflows/   # CI/CD (GitHub Actions)
└── docs/zenn-draft.md   # Zenn記事下書き
```

## 進捗ロードマップ

- [x] Step 1: Azure AI Search インデックス設計（チャンク分割方針・メタデータスキーマ・ハイブリッド検索設定）
- [x] Step 2: ダミー業務文書のチャンク化・埋め込み生成・インデックス投入パイプライン
- [ ] Step 3: Cosmos DB での会話履歴・セッション管理
- [ ] Step 4: RAG 回答生成ロジック（引用元提示含む）
- [ ] Step 5: Streamlit チャットUI
- [ ] Step 6: golden_qa 評価スクリプト（キーワード網羅率 / RAGAS）
- [ ] Step 7: Azure App Service デプロイ + GitHub Actions CI/CD
- [ ] Step 8: Bicep による IaC 化
- [ ] Zenn記事下書き・README整備

## セットアップ

> 各ステップの実装が進むにつれて随時更新します。

### 前提

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（依存関係・仮想環境管理）
- Azure サブスクリプション（Azure OpenAI / AI Search / Cosmos DB / App Service）

### 依存関係のインストール

```bash
uv sync
```

### 環境変数

`.env.example` をコピーして `.env` を作成し、Azure リソースの接続情報を設定してください（詳細は各ステップ実装時に追記）。

```bash
cp .env.example .env
```
