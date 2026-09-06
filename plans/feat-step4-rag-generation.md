# Step 4: Azure OpenAIを用いたRAG回答生成ロジック（引用元提示を含む）

関連Issue: #1

## スコープ

Step 1〜3で構築した「Azure AI Searchのハイブリッド検索インデックス」「ダミーERP文書」
「Cosmos DBセッション管理」を統合し、質問に対してAzure OpenAIで回答を生成する。
検索結果の引用元（タイトル・見出しパス・元ファイル名）を回答の番号参照と対応付けて提示する。

## 実装物

- `src/rag/search_client.py`: `hybrid_search` — ベクトル検索（`VectorizedQuery`）+
  キーワード検索 + セマンティックランカーを1リクエストで実行し、`SearchHit` のリストを返す。
  チャット応答では `chunk_strategy=heading_aware` を既定とする（見出し単位でまとまりが保たれ、
  引用元の`section_path`も直感的になるため）。`fixed_512`/`fixed_256`はStep6のgolden_qa評価で
  切り替えて比較する
- `src/rag/prompt_templates.py`: システムプロンプト（参考情報のみを根拠にする、根拠のない場合は
  正直に「回答できません」と述べる、各主張に`[1]`形式で出典番号を付記する、というルールを明記）と、
  検索結果を番号付き参考情報として組み立てる `build_user_message`
- `src/rag/citations.py`: `SearchHit` を Step 3 の `Citation`（Cosmos DBに保存する形）に変換する
  `build_citations`
- `src/rag/generator.py`: `generate_answer` — クエリ埋め込み→ハイブリッド検索→履歴取得→
  Azure OpenAI呼び出し→履歴保存、を一つの関数として統合する。戻り値の `RagAnswer` は
  回答テキストと引用元リストを持つ
- `scripts/ask_question.py`: 動作確認用CLI（1問1答、セッションIDを指定すれば履歴が引き継がれる）

## テスト方針

`hybrid_search`（`search_client.py`）・`build_citations`・`build_user_message` は
純粋なロジック、またはSDKクライアントを引数として受け取る薄いラッパーのため、フェイク
クライアント（`.search()`の戻り値と受け取ったkwargsを記録するだけの簡易オブジェクト）で
単体テストしている。`generate_answer`（配線部分）は単体テスト対象とせず、実リソースに
対する実行で動作確認した（Step2/3と同じ方針。Step7でのCI/CD継続検証方針は
`plans/feat-step2-ingestion-pipeline.md` 参照）。

```bash
uv run pytest tests/test_search_client.py tests/test_citations.py tests/test_prompt_templates.py -v
```

## 実リソースでの検証結果（2026-09-06）

```bash
uv run python scripts/ask_question.py "ERPNaviの初期設定はどこから始めればいいですか？" demo-step4-verify
uv run python scripts/ask_question.py "その後、会計年度はいつ決めればいいですか？" demo-step4-verify
```

- 1問目: 初期設定ガイドの該当セクション（テナント作成・会社情報登録・組織階層設定・チェックリスト）
  から正しく検索・引用され、手順が箇条書きで回答された
- 2問目（同一セッション）: 「その後」という省略された指示語を、履歴（1問目の文脈）を踏まえて
  正しく「初期設定の続き」と解釈し、会計年度設定について回答した。マルチターン対話の文脈保持を確認
- Cosmos DBへの保存確認: `get_history` で2ターンとも `citations` 付きで保存されていることを確認
  （turn 0: 引用5件、turn 1: 引用5件）

## 未確認・後続ステップに委ねる事項

- チャンク分割方針（`fixed_512`/`fixed_256`/`heading_aware`）ごとの回答精度の定量比較は
  Step 6（golden_qa評価）で実施する
- チャットUI（Step 5）からの利用、複数ユーザーの同時利用を想定した負荷特性は未検証
