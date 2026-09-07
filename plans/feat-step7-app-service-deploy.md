# Step 7（後半）: Azure App Serviceへのデプロイ + 環境変数管理・監視ログ設計

関連Issue: #1

## スコープ

PR #8（品質ゲート整備）で対象外とした、Azure App Serviceへの実デプロイ・環境変数管理・
簡易的な監視ログ設計を行う。

## リソース作成方針

Step1〜3のAzure OpenAI/AI Search/Cosmos DB同様、App Serviceリソース自体もAzureポータルで
ユーザーに作成してもらう方針とした。理由: このセッションからのAzure CLIログインで、
テナントのセキュリティ既定値によるブロックと、az-cli 2.90.0自体のバグ
（`_subscription_selector.py`でサブスクリプション0件時に`NoneType`に対して`.get()`を
呼び出しクラッシュする）の両方に遭遇し、CLIでのリソース作成が現実的でなかったため。

### 作成設定（実際に使用した値）

| 項目 | 値 |
|---|---|
| 公開 | コード |
| ランタイムスタック | Python 3.12 |
| OS | Linux |
| アプリ名 | `erp-navi-rag-demo`（URL: `erp-navi-rag-demo-fbcvagdpbsa6fbha.japanwest-01.azurewebsites.net`） |
| リージョン | **Japan West**（他リソースはJapan Eastだが、下記理由でWestに変更） |
| プラン | Basic (B1)、`plan-erp-navi-rag` |

**リージョンをJapan Eastから変更した理由**: 当初Japan East・B1で作成しようとしたところ、
`Microsoft.Web/serverFarms`のpreflight検証で失敗した。エラー詳細は
`Current Limit (Total VMs): 0` というVMクォータ不足で、F1（無料）に切り替えても
同じサブスクリプションのクォータ不足エラーが再現した。SKUではなくJapan East
リージョン側にこのサブスクリプション（Learning枠）のApp Service用コンピューティング
クォータが0で割り当てられていないことが原因と判断し、Japan Westに変更したところ
B1で正常に作成できた。他リソース（Azure OpenAI/AI Search/Cosmos DB）とリージョンが
分かれる結果になったが、Step1〜3で確認した通りAzure OpenAI/AI Search/Cosmos DBは
すべてJapan Eastで統一済みのため、App Serviceからこれらへのアクセスはリージョンを
跨ぐ形になる。この構成でのレイテンシは後述の動作確認で計測する。

### デプロイ後にポータルで設定が必要な項目

1. **起動コマンド**（設定 > 全般設定 > スタートアップコマンド）:
   ```
   python -m streamlit run src/app/streamlit_app.py --server.port ${PORT:-8000} --server.address 0.0.0.0 --server.headless true
   ```
2. **アプリケーション設定**（環境変数、`.env.example`と同じキー）:
   `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_API_VERSION` /
   `AZURE_OPENAI_CHAT_DEPLOYMENT` / `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` /
   `AZURE_SEARCH_ENDPOINT` / `AZURE_SEARCH_API_KEY` / `AZURE_SEARCH_INDEX_NAME` /
   `AZURE_COSMOS_ENDPOINT` / `AZURE_COSMOS_KEY` / `AZURE_COSMOS_DATABASE_NAME` /
   `AZURE_COSMOS_SESSIONS_CONTAINER`（値は手元の`.env`と同じ。Claude Codeセッションには
   一切共有していない）
3. `SCM_DO_BUILD_DURING_DEPLOYMENT=true`（zip deploy後にOryxが`requirements.txt`から
   ビルドするために必要）
4. Application Insightsの有効化（後述）

## デプロイ方式: 発行プロファイル + GitHub Actions

Azure CLI/Azure AD経由のOIDC連携は上記のテナント事情で構築が困難だったため、
発行プロファイル（Kudu基本認証）方式を採用した。

- ユーザーがポータルの「発行プロファイルの取得」でファイルをダウンロードし、
  その内容をGitHub Secretsの`AZURE_WEBAPP_PUBLISH_PROFILE`に登録
- アプリ名はGitHub Actions変数（Secretsではなく`vars`）の`AZURE_WEBAPP_NAME`に登録
  （機微情報ではないため）
- `.github/workflows/cd.yml`を新設。`main`へのpush（＝PRマージ）をトリガーに、
  `uv export --format requirements.txt --no-dev --no-hashes`でuv.lockから
  requirements.txtを都度生成し（コミットはしない、`.gitignore`に追加）、
  `azure/webapps-deploy@v3`でzipデプロイする

## 環境変数管理の方針

`.env`（ローカル開発用、Cosmos DB等の接続情報）とApp Serviceのアプリケーション設定
（本番用の同じ値）は別々に管理する。`src/config.py`は`python-dotenv`で`.env`を読むが、
`.env`が存在しない環境（App Service上）では素通りし、OS環境変数（アプリケーション設定は
実行時に環境変数として渡される）からそのまま読み込む設計になっている
（`load_dotenv()`は`.env`が無ければ何もしないため、追加のコード変更は不要だった）。

## 監視・ログ設計

- **Application Insights**: App Serviceの「Application Insights」画面から有効化するだけで、
  `APPLICATIONINSIGHTS_CONNECTION_STRING`がアプリケーション設定に自動追加され、
  リクエスト数・レスポンスタイム・例外を自動収集する（コード変更不要）
- **アプリケーションログ**: 「App Service ログ」でアプリケーションログ（ファイルシステム）を
  有効化すると、`logging`モジュール経由の出力（`src/app/streamlit_app.py`の
  `logger.exception(...)`等、Step5で機微情報を含めないよう設計済み）がログストリーム
  （`az webapp log tail`相当、ポータルの「ログストリーム」画面）で確認できる
- 機微情報（APIキー等）をログに出さない方針は、Step5で実装済みの`_generate_answer_safely`
  （例外詳細はログにのみ、画面には固定文言のみ）がそのまま本番でも有効

## 実装物

- `.github/workflows/cd.yml`: mainへのpushでApp Serviceへ自動デプロイ
- `.gitignore`: デプロイ時生成物`requirements.txt`を除外

## 動作確認

（ユーザーによるApp Service作成・GitHub Secrets/Vars設定後に追記）

## 未確認・後続ステップに委ねる事項

- OIDC federated credentialsへの移行（発行プロファイルより安全）は、テナント側の
  Azure AD操作権限が整理できた時点で再検討する
- 複数ユーザー同時アクセス時のB1プランでのスループット・レイテンシ特性は未検証
- Bicepによる App Service自体のプロビジョニングはStep 8で対応する
