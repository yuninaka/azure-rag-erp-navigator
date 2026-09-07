#!/usr/bin/env bash
# Bicepテンプレートの構文チェック(コンパイルのみ、実デプロイはしない)。
#
# 実デプロイ(az deployment group create)による動作確認はまだ行っていない
# (このセッションでのAzure CLIログインがテナントのセキュリティ既定値とaz-cliの
# バグの両方に阻まれたため。詳細は plans/feat-step7-app-service-deploy.md 参照)。
#
# 環境によってはBicep CLI(.NET製)がICUライブラリを要求し、"Couldn't find a valid
# ICU package" エラーで失敗することがある。DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true
# を設定して回避している(ロケール依存の文字列処理をしないBicepビルドでは実害がない)。
set -euo pipefail
export DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true

cd "$(dirname "$0")/.."

echo "==> az bicep install (未インストールの場合のみ)"
az bicep install >/dev/null 2>&1 || true

echo "==> bicep build: main.bicep"
az bicep build --file infra/bicep/main.bicep --stdout > /dev/null

echo "==> bicep build: modules/*.bicep"
for f in infra/bicep/modules/*.bicep; do
  echo "  $f"
  az bicep build --file "$f" --stdout > /dev/null
done

echo "==> bicep build-params: parameters/dev.bicepparam"
az bicep build-params --file infra/bicep/parameters/dev.bicepparam --stdout > /dev/null

echo "Bicep構文チェック完了"
