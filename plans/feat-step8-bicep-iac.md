# Step 8: BicepによるIaC化

関連Issue: #1

## スコープ

Step1〜7で個別にAzureポータルから作成したリソース（Azure OpenAI / AI Search / Cosmos DB /
App Service / 監視）を、Bicepで一括プロビジョニング可能な形にコード化する。

## 検証範囲（実デプロイは対象外）

`az bicep build` / `az bicep lint` によるコンパイル・静的チェックのみ実施し、
`az deployment group create` による実デプロイの動作確認は行っていない。理由:
Step7で実際に遭遇した通り、このセッションからのAzure CLIログインがテナントの
セキュリティ既定値によるブロックと、az-cli 2.90.0自体のバグ（`_subscription_selector.py`
でのクラッシュ）の両方に阻まれており、`az deployment`を安定して実行できる状態に
なかった。また、実デプロイを試みると既存リソースと重複作成される、または既存
リソースを意図せず上書き変更するリスクもあるため、今回は構文チェックに留める
判断をユーザーと確認した上で進めた。

## 実装物

```
infra/bicep/
├── main.bicep                    # エントリポイント、各モジュールを束ねる
├── modules/
│   ├── openai.bicep              # Azure OpenAIアカウント + chat/embeddingデプロイ
│   ├── search.bicep               # Azure AI Search
│   ├── cosmosdb.bicep             # Cosmos DBアカウント + database + sessionsコンテナ
│   ├── appservice.bicep           # App Service プラン + Web App(Linux, Python)
│   └── monitoring.bicep           # Log Analytics + Application Insights
└── parameters/
    └── dev.bicepparam             # パラメータファイル
```

- `scripts/validate_bicep.sh`: `az bicep build`/`build-params`をまとめて実行する構文チェックスクリプト

## 設計判断

### リージョンをリソースごとに個別パラメータ化

Step7で実際に遭遇した「Japan EastでApp ServiceのVMクォータが0でB1/F1とも作成失敗し、
Japan Westに変更して解決した」という制約を、Bicepのパラメータ既定値にもそのまま反映した
（`appServiceLocation`の既定値のみ`japanwest`、他は`japaneast`）。IaCコード自体が
「なぜリージョンが分かれているか」を説明するコメント付きで表現している。

### APIキーはBicep内で`listKeys()`により取得し、App Settingsへ直接注入

Azure OpenAI/AI Search/Cosmos DBのキーは、各モジュールが`listKeys()`
（AI Searchは`listAdminKeys()`）で取得し、`@secure()`出力としてmain.bicepに渡し、
App Serviceのアプリケーション設定に直接埋め込む設計にした。これにより、
`az deployment group create`を1回実行するだけで、リソース作成からApp Serviceへの
接続情報設定まで一気通貫で完結する。

**既知の制約（本番運用では非推奨）**: この方式はAPIキーがデプロイ履歴
（`az deployment group show`等）に残りうるという弱点がある。本番運用では
Key Vaultにキーを格納し、App ServiceはManaged Identity経由でKey Vault参照
（`@Microsoft.KeyVault(...)`構文）を使う設計にすべき。今回は検証用の
一括プロビジョニングのしやすさを優先し、簡略化した。この判断はコード内コメントにも明記した。

### モデル名・バージョンは既定値なしの必須パラメータ

Azure OpenAIのモデル提供状況・バージョンは頻繁に更新されるため、実在するか未確認の
値を既定値としてハードコードすることは避け、`chatModelName`/`chatModelVersion`/
`embeddingModelName`/`embeddingModelVersion`は既定値なしの必須パラメータとした。
`dev.bicepparam`にはプレースホルダー値を置き、デプロイ時点でAzureポータル/CLIで
確認してから値を埋めるようコメントで明記している。

### Cosmos DBの`defaultTtl: -1`

Step3で実装した`src/session/cosmos_client.py`と同じ設計判断（コンテナ全体には既定の
有効期限を設けず、アイテム個別の`ttl`フィールドで明示的に指定されたものだけを期限切れに
する）をBicep側にも反映した。

## 動作確認

```bash
./scripts/validate_bicep.sh
```

`main.bicep`・全モジュール・`dev.bicepparam`ともコンパイルエラー0件、lintも0件で通過した。

**環境メモ**: このセッションのサンドボックス環境ではBicep CLI（.NET製）が
ICUライブラリ不足で起動できず、`DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true`で
回避した（`scripts/validate_bicep.sh`内に組み込み済み）。

## 未確認・後続ステップに委ねる事項

- `az deployment group create`（または`what-if`）による実デプロイ検証は未実施。
  テナント側のAzure CLI認証問題が解消し次第、別リソースグループへの試験デプロイを
  検討する
- Key Vault + Managed Identityへの移行（`listKeys()`直接注入からの脱却）
- 既存の手動作成済みリソース（Step1〜7）とこのBicepテンプレートとの差分監査
  （実際のリソース名・SKU等がBicepの既定値と一致しているかの確認）は未実施
