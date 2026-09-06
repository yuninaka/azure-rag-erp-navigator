# Step 7（前半）: 「読まなくても壊れないコードベース」にするための品質ゲート整備

関連Issue: #1
参考: [レビューをやめた話](https://zenn.dev/singularity/articles/stopped-reviewing-my-code)

## スコープ

Step 7の本来のスコープ（Azure App Serviceデプロイ + GitHub Actions CI/CD）のうち、
まず「ローカルとCIで同じチェックを二段構えで実行する」品質ゲート整備を行った。
Azure App Serviceへの実デプロイは本ファイルの範囲外（別PRで対応）。

## 導入したツールと、何をゲートにして何をレポートに留めたか

| ツール | 役割 | ビルドを失敗させるか |
|---|---|---|
| pytest | 単体テスト | させる（ゲート） |
| ruff | lint（複雑度・型注釈必須化・命名・bugbear等） | させる（ゲート） |
| mypy（strict） | 静的型チェック | させる（ゲート） |
| vulture | デッドコード検出 | **させない**（レポートのみ、`\|\| true`） |

vultureを非ゲートにした理由: 動的な呼び出しパターン（Streamlitのコールバック登録、
dataclassのフィールド等）を誤検知しうるため。導入初日からビルドを失敗させる運用は
リスクが高いと判断し、まずは警告表示に留めた。将来誤検知がない状態が安定して確認できたら、
ゲート化を再検討する。

## 1. Ruffルール強化

`select`に`C90`(mccabe複雑度)・`PLR`(pylint refactor)・`N`(naming)・`B`(bugbear)・
`ANN`(型注釈必須化)を追加。導入直後は92件の違反があり、全て以下のいずれかで解消した。

- **型注釈の追加**（大半、約80件）: 関数の引数・戻り値に型注釈を追加。テストファイルも含めて
  全て手作業で注釈した（tests/を対象外にするper-file-ignoresは採用しなかった）
- **マジックナンバーの定数化**（約9件）: `assert x == 3`のような比較を
  `expected = 3; assert x == expected`の形に変更し、値の意味を名前で示した
- **設計変更**: `generate_answer`が引数過多（PLR0913, 10>6）だった。Azure接続一式
  （5引数）を`RagDependencies` dataclassにまとめる`src/rag/dependencies.py`を新設し、
  `eval/run_eval.py`・`src/app/streamlit_app.py`・`scripts/ask_question.py`の3箇所で
  重複していたクライアント組み立てロジックも同時に共通化した（実装前にこの分割方針を
  提示し、承認を得てから実施）

## 2. mypy strict導入

`strict = true`, `warn_unreachable = true`, `disallow_untyped_defs = true`を設定。
導入直後の9件のエラーは全て型を緩めずに解消し、`# type: ignore`を安易に使うことは
避けた。

- **TypedDict導入**: Cosmos DBのセッションメタデータ（`SessionMeta`）、Azure AI Search
  投入用ドキュメント（`SearchDocument`）を、動的な`dict`から構造化した型に変更
- **isinstanceによるナローイング**: YAMLフロントマターから読んだ`title`/`module_tags`を
  `SourceDocument`（dataclass）に渡す前に型を検証
- **`# type: ignore`（2箇所、理由コメント付き）**: `azure-search-documents`が実行時に
  monkey-patchで追加する`SearchFieldDataType.Collection`は、mypyの静的解析からは
  呼び出し不可能なEnumに見える。ライブラリ側の実装詳細であり当方では修正不可のため
- **`cast`（3箇所、いずれもSDK境界でのみ使用）**: (1)Cosmos DBの動的な応答を
  `SessionMeta`とみなす境界、(2)OpenAI SDKが要求するリテラル型Unionと
  `list[dict[str, str]]`の不一致、(3)`SearchDocument`(TypedDict)を
  `upload_documents`が要求する`list[dict[Any, Any]]`に渡す境界。いずれも
  読み書き双方を自コードが管理しており、実際のデータ形状を保証できる箇所のみに限定した

**mypy strict化の残課題**: なし。`mypy src`は0エラーの状態まで到達した
（`tests/`・`scripts/`・`eval/`はci_check.shの対象外としており未チェック）。

## 3. vulture（デッドコード検出）

導入直後、`src/ingestion/ingest_pipeline.py`で`Any`の未使用importが1件検出された
（文字列指定の`cast("list[dict[Any, Any]]", ...)`によりvultureの静的解析からは
使用箇所が見えていなかった）。`cast`の型引数を非文字列形式（`cast(list[dict[Any, Any]], ...)`）
に変更し、mypyの解釈は変えずにvultureからも使用が見える形にして解消した。

## 4〜5. 共通チェックスクリプトとGitHub Actions

`scripts/ci_check.sh`（pytest→ruff→mypy→vulture(report-only)の順で実行、`set -euo pipefail`で
途中失敗時に即座に終了）を新設し、`.github/workflows/ci.yml`はこのスクリプトを呼び出すだけの
薄いラッパーにした。チェック内容の変更は必ず`ci_check.sh`側で行い、ワークフロー側に個別コマンドを
追記しない、というルールをCLAUDE.mdに明記した。

Azure実リソースへの疎通確認（`scripts/verify_azure_connectivity.py`）は、シークレット管理・
コストの観点から`ci_check.sh`には含めず、手動実行のままとした。

## 6. CLAUDE.md

リポジトリ直下に新設。PR前のci_check.sh実行、テストカバレッジの観点（過去に実際に見つかった
6件のバグを具体例として記載）、pure/IO分離方針、noqa/type:ignoreの運用ルール、機微情報を
出力しない方針を明文化した。

## 動作確認

```bash
./scripts/ci_check.sh
```

pytest 46件・ruff・mypyすべてPASS、vultureも指摘0件で完走した（exit code 0）。

## 未確認・後続ステップに委ねる事項

- Azure App Serviceへの実デプロイ、環境変数管理（App Service側のApplication Settings）、
  監視・ログ設計（Application Insights連携）は本PRの範囲外。別途Step7後半として対応する
- GitHub Actionsのワークフローは`pull_request`トリガーのみで、実際にPRを作成してCI上での
  動作確認はまだ行っていない（次のPR作成時に確認する）
- vultureを将来ゲート化するかどうかは、誤検知の有無を見ながら再検討する
