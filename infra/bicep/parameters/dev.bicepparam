using '../main.bicep'

param projectName = 'erp-navi-rag'
param environmentName = 'dev'

// デプロイ時点でAzureポータルの「Azure OpenAI Studio(Foundry) > デプロイ」または
// `az cognitiveservices account list-models` で、対象リージョンに実際に利用可能な
// モデル名・バージョンを確認してから設定すること。モデルの提供状況は頻繁に更新されるため、
// このファイルには値を固定していない。
param chatModelName = '<例: gpt-4.1-mini。デプロイ時点で利用可能なモデル名を指定>'
param chatModelVersion = '<デプロイ時点の最新バージョンを指定>'
param embeddingModelName = '<例: text-embedding-3-large>'
param embeddingModelVersion = '<デプロイ時点の最新バージョンを指定>'

param appServicePlanSkuName = 'B1'
