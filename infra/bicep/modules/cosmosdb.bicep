@description('Cosmos DBを作成するリージョン')
param location string

@description('Cosmos DBアカウント名(グローバルに一意)')
param accountName string

@description('データベース名')
param databaseName string

@description('セッション履歴を格納するコンテナ名')
param sessionsContainerName string

@description('sessionsコンテナのパーティションキー')
param sessionsPartitionKeyPath string = '/sessionId'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// defaultTtl: -1 は「コンテナ全体には既定の有効期限を設けないが、アイテム個別の ttl
// フィールドで明示的に指定されたものだけを期限切れにする」設定(src/session/history_manager.py
// と同じ設計。plans/feat-step3-cosmos-session-management.md参照)。
resource sessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: sessionsContainerName
  properties: {
    resource: {
      id: sessionsContainerName
      partitionKey: {
        paths: [
          sessionsPartitionKeyPath
        ]
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

output endpoint string = cosmosAccount.properties.documentEndpoint
output accountName string = cosmosAccount.name

@secure()
@description('Cosmos DBのプライマリキー(App ServiceのApplication Settingsに直接注入する用。本番運用ではKey Vault参照+Managed Identityを推奨)')
output primaryKey string = cosmosAccount.listKeys().primaryMasterKey
