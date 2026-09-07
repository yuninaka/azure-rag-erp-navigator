// azure-rag-erp-navigator のAzureリソース一式(Azure OpenAI / AI Search / Cosmos DB /
// App Service / 監視)をプロビジョニングするエントリポイント。
//
// 実際の検証(Step1〜7)で使用したリソースはAzureポータルで個別に作成したものであり、
// このBicepはそれを事後的にコード化したもの。構文チェック(`az bicep build`)のみ実施し、
// 実デプロイ(`az deployment group create`)による動作確認はまだ行っていない
// (このセッションでのAzure CLIログインがテナットのセキュリティ既定値とaz-cliのバグの
// 両方に阻まれたため。詳細は plans/feat-step7-app-service-deploy.md 参照)。
targetScope = 'resourceGroup'

@description('プロジェクト名(リソース名のプレフィックスに使用)')
param projectName string = 'erp-navi-rag'

@description('環境名(dev/prod等)')
param environmentName string = 'dev'

@description('Azure OpenAIのリージョン')
param openAiLocation string = 'japaneast'

@description('Azure AI Searchのリージョン')
param searchLocation string = 'japaneast'

@description('Cosmos DBのリージョン')
param cosmosLocation string = 'japaneast'

@description('監視リソース(Log Analytics/Application Insights)のリージョン')
param monitoringLocation string = 'japaneast'

// 既定値をjapanwestにしているのは、実際の検証でjapaneast・B1プランのApp Service作成が
// 「Current Limit (Total VMs): 0」というVMクォータ不足のpreflightエラーで失敗し、
// F1(無料)に切り替えても再現したため。SKUではなくリージョン側のクォータ制約と判断し、
// japanwestに変更したところ解決した。他リソースとリージョンが分かれる結果になっている。
// 詳細は plans/feat-step7-app-service-deploy.md 参照。
@description('App Serviceのリージョン。既定はjapaneastでのVMクォータ制約を回避したjapanwest')
param appServiceLocation string = 'japanwest'

@description('チャット用モデル名。デプロイ時点でリージョンに利用可能なモデルをAzureポータル/CLIで確認して指定する')
param chatModelName string

@description('チャット用モデルバージョン。モデルは定期的に新バージョンが出るため、デプロイ時点の最新値を確認して指定する')
param chatModelVersion string

@description('埋め込み用モデル名')
param embeddingModelName string

@description('埋め込み用モデルバージョン')
param embeddingModelVersion string

@description('App Service プランのSKU。B1推奨(F1はサブスクリプションによってはVMクォータ不足で使えない)')
param appServicePlanSkuName string = 'B1'

var chatDeploymentName = 'gpt-chat'
var embeddingDeploymentName = 'text-embedding'
var openAiAccountName = '${projectName}-openai-${environmentName}'
var searchServiceName = '${projectName}-search-${environmentName}'
var cosmosAccountName = '${projectName}-cosmos-${environmentName}'
var cosmosDatabaseName = 'erp-navigator'
var cosmosSessionsContainerName = 'sessions'
var searchIndexName = 'erp-knowledge-index'
var appServicePlanName = 'plan-${projectName}-${environmentName}'
var appServiceName = '${projectName}-demo-${environmentName}'
var logAnalyticsName = '${projectName}-logs-${environmentName}'
var appInsightsName = '${projectName}-insights-${environmentName}'
// App Serviceの起動コマンド(README/plans記載のものと同一)。Bicep文字列補間との
// 衝突を避けるため `$` をエスケープし、シェル変数展開の `${PORT:-8000}` をそのまま出力する。
var appStartupCommand = 'python -m streamlit run src/app/streamlit_app.py --server.port \${PORT:-8000} --server.address 0.0.0.0 --server.headless true'

module openAi 'modules/openai.bicep' = {
  name: 'openAiDeployment'
  params: {
    location: openAiLocation
    accountName: openAiAccountName
    chatDeploymentName: chatDeploymentName
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    embeddingDeploymentName: embeddingDeploymentName
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
  }
}

module search 'modules/search.bicep' = {
  name: 'searchDeployment'
  params: {
    location: searchLocation
    serviceName: searchServiceName
  }
}

module cosmos 'modules/cosmosdb.bicep' = {
  name: 'cosmosDeployment'
  params: {
    location: cosmosLocation
    accountName: cosmosAccountName
    databaseName: cosmosDatabaseName
    sessionsContainerName: cosmosSessionsContainerName
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    location: monitoringLocation
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
  }
}

module appService 'modules/appservice.bicep' = {
  name: 'appServiceDeployment'
  params: {
    location: appServiceLocation
    planName: appServicePlanName
    appName: appServiceName
    planSkuName: appServicePlanSkuName
    startupCommand: appStartupCommand
    appSettings: {
      AZURE_OPENAI_ENDPOINT: openAi.outputs.endpoint
      AZURE_OPENAI_API_KEY: openAi.outputs.primaryKey
      AZURE_OPENAI_API_VERSION: '2024-10-21'
      AZURE_OPENAI_CHAT_DEPLOYMENT: chatDeploymentName
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embeddingDeploymentName
      AZURE_SEARCH_ENDPOINT: search.outputs.endpoint
      AZURE_SEARCH_API_KEY: search.outputs.primaryKey
      AZURE_SEARCH_INDEX_NAME: searchIndexName
      AZURE_COSMOS_ENDPOINT: cosmos.outputs.endpoint
      AZURE_COSMOS_KEY: cosmos.outputs.primaryKey
      AZURE_COSMOS_DATABASE_NAME: cosmosDatabaseName
      AZURE_COSMOS_SESSIONS_CONTAINER: cosmosSessionsContainerName
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
    }
  }
}

output appServiceUrl string = 'https://${appService.outputs.defaultHostName}'
output openAiEndpoint string = openAi.outputs.endpoint
output searchEndpoint string = search.outputs.endpoint
output cosmosEndpoint string = cosmos.outputs.endpoint
