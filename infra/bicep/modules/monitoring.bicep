@description('監視リソースを作成するリージョン')
param location string

@description('Log Analyticsワークスペース名')
param logAnalyticsName string

@description('Application Insightsリソース名')
param appInsightsName string

@description('ログ保持日数')
param retentionInDays int = 30

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

output logAnalyticsWorkspaceId string = logAnalytics.id

@secure()
@description('App Serviceの APPLICATIONINSIGHTS_CONNECTION_STRING に設定する接続文字列')
output connectionString string = appInsights.properties.ConnectionString
