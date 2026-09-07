@description('Azure OpenAIリソースを作成するリージョン')
param location string

@description('Azure OpenAIアカウント名(グローバルに一意である必要はないが、Cognitive Servicesリソース名として一意)')
param accountName string

@description('Azure OpenAIのSKU。通常はS0')
param skuName string = 'S0'

@description('チャット用デプロイ名(アプリの AZURE_OPENAI_CHAT_DEPLOYMENT と一致させる)')
param chatDeploymentName string

@description('チャット用モデル名。デプロイ時点でリージョンに利用可能なモデルをAzureポータル/CLIで確認して指定する')
param chatModelName string

@description('チャット用モデルバージョン。モデルは定期的に新バージョンが出るため、デプロイ時点の最新値を確認して指定する')
param chatModelVersion string

@description('埋め込み用デプロイ名(アプリの AZURE_OPENAI_EMBEDDING_DEPLOYMENT と一致させる)')
param embeddingDeploymentName string

@description('埋め込み用モデル名')
param embeddingModelName string

@description('埋め込み用モデルバージョン')
param embeddingModelVersion string

@description('各デプロイのキャパシティ(TPM単位、1000トークン/分単位)。既定値は検証用の小さめの値')
param deploymentCapacity int = 10

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  sku: {
    name: skuName
  }
  kind: 'OpenAI'
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: chatDeploymentName
  sku: {
    name: 'Standard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
}

// 同一アカウントへの複数デプロイを並行作成すると競合することがあるため、明示的に直列化する。
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: embeddingDeploymentName
  sku: {
    name: 'Standard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
  dependsOn: [
    chatDeployment
  ]
}

output endpoint string = openAiAccount.properties.endpoint
output accountName string = openAiAccount.name

@secure()
@description('Azure OpenAIアカウントのAPIキー(App ServiceのApplication Settingsに直接注入する用。本番運用ではKey Vault参照+Managed Identityを推奨)')
output primaryKey string = openAiAccount.listKeys().key1
