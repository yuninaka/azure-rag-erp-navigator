@description('App Serviceを作成するリージョン')
param location string

@description('App Service プラン名')
param planName string

@description('Web App名(グローバルに一意。URLの一部になる)')
param appName string

@description('App Service プランのSKU')
param planSkuName string = 'B1'

@description('起動コマンド')
param startupCommand string

@secure()
@description('アプリケーション設定(環境変数)。キーと値のマップ。APIキー等の機微な値を含むためsecureにしている')
param appSettings object

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planName
  location: location
  sku: {
    name: planSkuName
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: startupCommand
      alwaysOn: true
      appSettings: [
        for setting in items(appSettings): {
          name: setting.key
          value: setting.value
        }
      ]
    }
  }
}

output defaultHostName string = webApp.properties.defaultHostName
output appName string = webApp.name
