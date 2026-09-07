@description('Azure AI Searchを作成するリージョン')
param location string

@description('Azure AI Searchサービス名(グローバルに一意)')
param serviceName string

@description('SKU。ハイブリッド検索・セマンティックランカーにはbasic以上が必要')
param skuName string = 'basic'

@description('セマンティックランカーの課金階層')
param semanticSearchTier string = 'free'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: serviceName
  location: location
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: semanticSearchTier
  }
}

output endpoint string = 'https://${searchService.name}.search.windows.net'
output serviceName string = searchService.name

@secure()
@description('Azure AI Searchの管理者キー(App ServiceのApplication Settingsに直接注入する用。本番運用ではKey Vault参照+Managed Identityを推奨)')
output primaryKey string = searchService.listAdminKeys().primaryKey
